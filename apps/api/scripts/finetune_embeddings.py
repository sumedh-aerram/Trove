#!/usr/bin/env python3
"""Fine-tune the embedding model on real click/star pairs (the recall lever).

Retrieval recall is the bottleneck and it is set by the bi-encoder. The most
effective fix is to fine-tune that encoder on (query, clicked-doc) pairs with
Multiple Negatives Ranking Loss (MNRL) plus hard-negative mining.

Pipeline (research-standard, see sentence-transformers + NV-Retriever):
  1. Positives: (query -> clicked/starred artifact text) from feedback_pairs.json.
  2. Hard negatives: for each query, retrieve top candidates with the CURRENT
     model and take similar-but-not-clicked docs as negatives.
  3. False-negative filter: drop any "negative" scoring within 95% of the
     positive's similarity (it is probably a real match, just unlabeled).
  4. Train with MNRL (temperature ~0.05), 1-3 epochs, small batches.

Gated on data volume: MNRL overfits fast, so it refuses to run until there are
enough pairs. With little data it prints what is missing and exits. After
training, re-embed the corpus and point EMBEDDING_MODEL_NAME at the new dir.

Run (from apps/api):
  DATABASE_URL=... PYTHONPATH=. python scripts/finetune_embeddings.py
"""
from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db import close_pool, fetch, init_pool  # noqa: E402
from scripts.eval_data import load_feedback_pairs  # noqa: E402

MIN_PAIRS = 200          # MNRL overfits on tiny sets; refuse below this
HARD_NEGS = 5
FALSE_NEG_THRESHOLD = 0.95  # drop negatives scoring >= 95% of the positive
OUT_DIR = Path(__file__).resolve().parents[1] / "models" / "trove-embed-ft"


def _doc_text(r: dict) -> str:
    parts = [r.get("title") or "", r.get("summary") or "", r.get("what_it_helps_build") or ""]
    return " ".join(p for p in parts if p)[:512]


async def main() -> None:
    pairs = load_feedback_pairs()
    if len(pairs) < MIN_PAIRS:
        print(
            f"Only {len(pairs)} feedback pairs (need >= {MIN_PAIRS}).\n"
            "Embedding fine-tuning is gated until there is enough real click/star\n"
            "data, because contrastive training overfits on tiny sets. Keep the\n"
            "loop running (searches + clicks + stars) and re-run this later.\n"
            "Until then, the tuned hybrid + LambdaMART pipeline is the best config."
        )
        return

    await init_pool()
    try:
        import numpy as np
        from sentence_transformers import InputExample, SentenceTransformer, losses
        from sentence_transformers.util import cos_sim
        from torch.utils.data import DataLoader

        rows = await fetch(
            "SELECT id, title, summary, what_it_helps_build FROM artifacts"
        )
        text_by_id = {str(r["id"]): _doc_text(dict(r)) for r in rows}

        # group positives per query
        pos_by_query: dict[str, list[str]] = defaultdict(list)
        for p in pairs:
            if p["positive_id"] in text_by_id:
                pos_by_query[p["query"]].append(p["positive_id"])

        model = SentenceTransformer(get_settings().embedding_model_name)

        # encode the corpus once for mining (cap for memory on large catalogs)
        cand_ids = list(text_by_id.keys())[:20000]
        cand_emb = model.encode([text_by_id[c] for c in cand_ids],
                                convert_to_numpy=True, normalize_embeddings=True, batch_size=128)

        examples: list = []
        for query, pos_ids in pos_by_query.items():
            q_emb = model.encode(query, convert_to_numpy=True, normalize_embeddings=True)
            sims = cos_sim(q_emb, cand_emb).numpy().ravel()
            for pid in pos_ids:
                pos_text = text_by_id[pid]
                p_emb = model.encode(pos_text, convert_to_numpy=True, normalize_embeddings=True)
                pos_sim = float(np.dot(q_emb, p_emb))
                # hard negatives: most similar candidates, minus false negatives
                order = np.argsort(-sims)
                taken = 0
                for idx in order:
                    cid = cand_ids[idx]
                    if cid in pos_ids:
                        continue
                    if float(sims[idx]) >= FALSE_NEG_THRESHOLD * pos_sim:
                        continue  # likely an unlabeled true positive
                    examples.append(InputExample(texts=[query, pos_text, text_by_id[cid]]))
                    taken += 1
                    if taken >= HARD_NEGS:
                        break

        if not examples:
            print("No usable training triplets after filtering. Exiting.")
            return

        loader = DataLoader(examples, shuffle=True, batch_size=16)
        loss = losses.MultipleNegativesRankingLoss(model)
        model.fit(train_objectives=[(loader, loss)], epochs=2, warmup_steps=10, show_progress_bar=True)

        OUT_DIR.parent.mkdir(exist_ok=True)
        model.save(str(OUT_DIR))
        print(f"\nSaved fine-tuned embedding model -> {OUT_DIR}")
        print(
            "Next steps:\n"
            f"  1. Set EMBEDDING_MODEL_NAME={OUT_DIR} in .env\n"
            "  2. Re-embed the corpus (workers embedding backfill) so artifact\n"
            "     vectors match the new model.\n"
            "  3. Run scripts/eval_search.py to confirm recall improved before shipping."
        )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
