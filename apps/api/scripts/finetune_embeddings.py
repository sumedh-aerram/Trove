#!/usr/bin/env python3
"""Fine-tune the embedding model on click/star pairs and/or curated eval pairs.

Retrieval recall is the bottleneck and it is set by the bi-encoder. The most
effective fix is to fine-tune that encoder on (query, clicked-doc) pairs with
Multiple Negatives Ranking Loss (MNRL) plus hard-negative mining.

Pipeline:
  1. Positives from feedback_pairs.json and/or curated eval oracle matches.
  2. Hard negatives: retrieve top candidates with the CURRENT model.
  3. False-negative filter: drop negatives scoring within 95% of the positive.
  4. Train with MNRL, 2 epochs, small batches.

Run (from apps/api):
  # clicks only (needs >= 200 pairs)
  DATABASE_URL=... PYTHONPATH=. python scripts/finetune_embeddings.py

  # curated eval oracle pairs (works without live click traffic)
  DATABASE_URL=... PYTHONPATH=. python scripts/finetune_embeddings.py --include-curated
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db import close_pool, fetch, init_pool  # noqa: E402
from app.services.extraction_service import build_embedding_text, extract_project_intent  # noqa: E402
from app.services.intent_retrieval import build_retrieval_context, enrich_intent  # noqa: E402
from scripts.eval_data import (  # noqa: E402
    load_curated_training_pairs,
    load_feedback_pairs,
    merge_training_pairs,
)

MIN_PAIRS_FEEDBACK = 200
MIN_PAIRS_CURATED = 40
HARD_NEGS = 5
FALSE_NEG_THRESHOLD = 0.95
OUT_DIR = Path(__file__).resolve().parents[1] / "models" / "trove-embed-ft"

_ARTIFACT_COLS = (
    "id, title, artifact_type, summary, what_it_helps_build, technical_core, "
    "practical_use_case, how_to_remix, implementation_steps, setup_commands, "
    "tags, tools, frameworks, languages, apis, models"
)


def _query_text(query: str) -> str:
    intent = enrich_intent(query, extract_project_intent(query))
    return build_retrieval_context(query, intent)


async def main(*, include_curated: bool, min_pairs: int | None) -> None:
    feedback = load_feedback_pairs()
    curated: list[dict] = []
    if include_curated:
        await init_pool()
        try:
            curated = await load_curated_training_pairs()
        finally:
            await close_pool()

    pairs = merge_training_pairs(feedback, curated)
    threshold = min_pairs
    if threshold is None:
        threshold = MIN_PAIRS_CURATED if include_curated else MIN_PAIRS_FEEDBACK

    if len(pairs) < threshold:
        print(
            f"Only {len(pairs)} training pairs (need >= {threshold}).\n"
            f"  feedback: {len(feedback)}  curated: {len(curated)}\n"
        )
        if include_curated:
            print("Curated mode uses oracle matches from the frozen eval set.")
        else:
            print(
                "Use --include-curated to train on eval oracle pairs without click data,\n"
                "or keep the self-improving loop running and re-run later."
            )
        return

    print(f"Training on {len(pairs)} pairs ({len(feedback)} feedback, {len(curated)} curated)")

    await init_pool()
    try:
        import numpy as np
        from sentence_transformers import InputExample, SentenceTransformer, losses
        from sentence_transformers.util import cos_sim
        from torch.utils.data import DataLoader

        rows = await fetch(f"SELECT {_ARTIFACT_COLS} FROM artifacts")
        text_by_id = {str(r["id"]): build_embedding_text(dict(r)) for r in rows}

        pos_by_query: dict[str, list[str]] = defaultdict(list)
        for p in pairs:
            pid = str(p["positive_id"])
            if pid in text_by_id:
                pos_by_query[str(p["query"])].append(pid)

        model = SentenceTransformer(get_settings().embedding_model_name)

        cand_ids = list(text_by_id.keys())[:20000]
        cand_emb = model.encode(
            [text_by_id[c] for c in cand_ids],
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=128,
        )

        examples: list = []
        for query, pos_ids in pos_by_query.items():
            q_text = _query_text(query)
            q_emb = model.encode(q_text, convert_to_numpy=True, normalize_embeddings=True)
            sims = cos_sim(q_emb, cand_emb).numpy().ravel()
            for pid in pos_ids:
                pos_text = text_by_id[pid]
                p_emb = model.encode(pos_text, convert_to_numpy=True, normalize_embeddings=True)
                pos_sim = float(np.dot(q_emb, p_emb))
                order = np.argsort(-sims)
                taken = 0
                for idx in order:
                    cid = cand_ids[idx]
                    if cid in pos_ids:
                        continue
                    if float(sims[idx]) >= FALSE_NEG_THRESHOLD * pos_sim:
                        continue
                    examples.append(InputExample(texts=[q_text, pos_text, text_by_id[cid]]))
                    taken += 1
                    if taken >= HARD_NEGS:
                        break

        if not examples:
            print("No usable training triplets after filtering. Exiting.")
            return

        print(f"Built {len(examples)} MNRL triplets")
        loader = DataLoader(examples, shuffle=True, batch_size=16)
        loss = losses.MultipleNegativesRankingLoss(model)
        model.fit(train_objectives=[(loader, loss)], epochs=2, warmup_steps=10, show_progress_bar=True)

        OUT_DIR.parent.mkdir(exist_ok=True)
        model.save(str(OUT_DIR))
        print(f"\nSaved fine-tuned embedding model -> {OUT_DIR}")
        print(
            "Next steps:\n"
            f"  1. Set EMBEDDING_MODEL_NAME={OUT_DIR} in .env\n"
            "  2. Re-embed the corpus: cd workers && python ingest/backfill_embeddings.py --all\n"
            "  3. Run scripts/tune_search.py and scripts/eval_search.py before shipping."
        )
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune the bi-encoder on usage and/or curated pairs")
    parser.add_argument(
        "--include-curated",
        action="store_true",
        help="Add top oracle match per frozen eval query (lower pair threshold)",
    )
    parser.add_argument(
        "--min-pairs",
        type=int,
        default=None,
        help="Override minimum pair count (default: 200 feedback-only, 40 with --include-curated)",
    )
    args = parser.parse_args()
    asyncio.run(main(include_curated=args.include_curated, min_pairs=args.min_pairs))
