"""
Retrieval over the existing ChromaDB knowledge base.

Unchanged: embedding model (all-MiniLM-L6-v2, normalised), Chroma collection
and its cosine HNSW index, so the existing 33k-chunk index is reused as-is.

Improvements:
* Lazy initialisation (the API can start and report readiness even if the
  vector store is temporarily unavailable).
* Over-fetch then de-duplicate: the corpus contains several duplicated PDFs,
  which previously filled the top-k with identical passages.
* Relevance threshold: passages beyond RETRIEVAL_MAX_DISTANCE are dropped
  instead of being presented to the LLM as "supporting" evidence.
* Human-readable titles from the ingestion mapping file (never invented).
"""

from __future__ import annotations

import csv
import hashlib
import logging
import re
import threading
from functools import lru_cache

from app.config import settings

logger = logging.getLogger("coach.retriever")

_lock = threading.Lock()
_model = None
_collection = None


def _init():
    global _model, _collection
    if _collection is not None:
        return
    with _lock:
        if _collection is not None:
            return
        import chromadb
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=str(settings.resolve(settings.CHROMA_PATH)))
        collection = client.get_collection(name=settings.COLLECTION_NAME)
        _model, _collection = model, collection
        logger.info("Knowledge base loaded: %s chunks", collection.count())


def get_collection():
    _init()
    return _collection


def chunk_count() -> int:
    return get_collection().count()


@lru_cache(maxsize=1)
def _titles() -> dict[str, str]:
    path = settings.resolve(settings.TITLE_MAPPING_FILE)
    titles: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                original = (row.get("OriginalName") or "").strip()
                new = (row.get("NewName") or "").strip()
                if new and original:
                    stem = re.sub(r"\.pdf$", "", original, flags=re.I)
                    titles[new] = re.sub(r"[_]+", " ", stem).strip()
    except FileNotFoundError:
        logger.warning("Title mapping file not found: %s", path)
    return titles


def title_for(document: str) -> str | None:
    return _titles().get(document)


def _doc_key(title: str | None, document: str) -> str:
    """Normalise titles so duplicated uploads ('X', 'X (1)', 'X copy') count as one document."""
    key = (title or document).lower()
    key = re.sub(r"\s*(\(\d+\)|copy)\s*$", "", key)
    return re.sub(r"\W+", " ", key).strip()


def _fingerprint(text: str) -> str:
    norm = re.sub(r"\W+", " ", text.lower()).strip()
    return hashlib.sha1(norm[:600].encode("utf-8")).hexdigest()


def retrieve_context(question: str, top_k: int | None = None) -> list[dict]:
    """Return up to top_k relevant, de-duplicated passages (blocking call)."""
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []

    top_k = top_k or settings.RETRIEVAL_TOP_K
    fetch_k = min(max(settings.RETRIEVAL_FETCH_K, top_k), total)

    embedding = _model.encode([question], normalize_embeddings=True).tolist()
    results = collection.query(
        query_embeddings=embedding,
        n_results=fetch_k,
        include=["documents", "metadatas", "distances"],
    )

    seen_text: set[str] = set()
    seen_page: set[tuple[str, int]] = set()
    per_doc: dict[str, int] = {}
    passages: list[dict] = []

    for text, meta, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        if distance > settings.RETRIEVAL_MAX_DISTANCE:
            continue
        fp = _fingerprint(text)
        source = meta.get("source", "unknown")
        page = int(meta.get("page", 0))
        title = title_for(source)
        # Duplicate PDFs share (normalised) titles; same title+page = same passage.
        doc = _doc_key(title, source)
        page_key = (doc, page)
        if fp in seen_text or page_key in seen_page:
            continue
        # Diversity: at most MAX_PER_DOCUMENT passages from one document.
        if per_doc.get(doc, 0) >= settings.RETRIEVAL_MAX_PER_DOCUMENT:
            continue
        seen_text.add(fp)
        seen_page.add(page_key)
        per_doc[doc] = per_doc.get(doc, 0) + 1
        passages.append(
            {
                "text": text,
                "document": source,
                "title": title,
                "page": page,
                "distance": float(distance),
            }
        )
        if len(passages) >= top_k:
            break

    return passages
