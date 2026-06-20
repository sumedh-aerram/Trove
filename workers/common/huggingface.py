"""Map Hugging Face Hub model records to artifacts.

Models are high-substance, ready-to-use building blocks (there is always usage
code and a model card), which is exactly the kind of result Trove should rank
well. We use only the public Hub list API (JSON, no model download).
"""
from __future__ import annotations

import math
from typing import Any

from .paths import *  # noqa: F403

from app.services.embedding_service import embed_text
from app.services.extraction_service import build_embedding_text, infer_fields_from_text
from app.services.scoring_service import score_all
from app.utils.text import slugify, truncate
from app.utils.urls import canonicalize_url

# Map HF pipeline tags to a human "what you can build" line.
_TASK_HELP = {
    "text-to-speech": "Add natural speech output (TTS) to an app.",
    "automatic-speech-recognition": "Transcribe audio/video (STT) in your project.",
    "text-generation": "Run a local/open LLM for chat, agents, or generation.",
    "text-to-image": "Generate images from prompts in your app.",
    "image-to-text": "Caption or read images (OCR/VQA) in a pipeline.",
    "sentence-similarity": "Power semantic search / RAG retrieval with embeddings.",
    "feature-extraction": "Generate embeddings for search, clustering, or RAG.",
    "summarization": "Summarize long documents or transcripts.",
    "translation": "Add multilingual translation.",
    "object-detection": "Detect objects in images/video.",
    "image-segmentation": "Segment images for vision features.",
    "question-answering": "Answer questions over a context passage.",
    "zero-shot-classification": "Classify text into arbitrary labels with no training.",
    "fill-mask": "Use a masked LM backbone for NLP features.",
    "text-classification": "Classify or score text (sentiment, intent, moderation).",
}


def hf_model_to_artifact(model: dict[str, Any]) -> dict[str, Any]:
    model_id = model.get("id") or model.get("modelId") or ""
    url = f"https://huggingface.co/{model_id}"
    pipeline = (model.get("pipeline_tag") or "").strip()
    hub_tags = [t for t in (model.get("tags") or []) if isinstance(t, str)]
    library = model.get("library_name") or ""
    downloads = int(model.get("downloads") or 0)
    likes = int(model.get("likes") or 0)

    help_line = _TASK_HELP.get(pipeline, "A ready-to-use model you can drop into a project.")
    summary = (
        f"{model_id} is a {pipeline or 'model'} on Hugging Face"
        + (f" ({library})" if library else "")
        + f". {help_line} {downloads:,} downloads, {likes} likes."
        + (f" Tags: {', '.join(hub_tags[:8])}." if hub_tags else "")
    )

    inferred = infer_fields_from_text(model_id, summary, " ".join(hub_tags))
    frameworks = inferred.get("frameworks", [])
    if library and library not in frameworks:
        frameworks = frameworks + [library]

    artifact: dict[str, Any] = {
        "title": model_id[:300],
        "slug": slugify(model_id.replace("/", "-")),
        "source_type": "huggingface",
        "artifact_type": "model",
        "source_url": url,
        "canonical_url": canonicalize_url(url),
        "author_name": model_id.split("/")[0] if "/" in model_id else None,
        "summary": truncate(summary, 600),
        "what_it_helps_build": help_line,
        "technical_core": truncate(summary, 800),
        "practical_use_case": help_line,
        "how_to_remix": (
            "Install transformers/diffusers (or the listed library), load the model "
            "by its id, and call it from your code. See the model card for usage."
        ),
        "tags": list(dict.fromkeys(inferred.get("tags", []) + [pipeline] if pipeline else inferred.get("tags", []))) + ["huggingface", "model"],
        "tools": list(dict.fromkeys(inferred.get("tools", []) + (["transformers"] if "transformers" in (library or "") else []))),
        "frameworks": frameworks,
        "languages": inferred.get("languages", []),
        "models": [model_id],
        "has_code": True,
        "has_docs": True,
        "has_demo": False,
        # log-scaled popularity from downloads (0..100).
        "popularity_score": min(100.0, 10.0 * math.log10(downloads + 1)),
    }
    score_all(artifact)
    artifact["embedding_vector"] = embed_text(build_embedding_text(artifact))
    return artifact
