# =============================================================================
# embedding_cache.py
# Skips redundant embedding API calls by hashing document content first.
#
# Project : Token Cost Anatomy
# Author  : Shannon Eldridge-Kuehn
# Blog    : https://shankuehn.io
# Created : 2026-07-09
# Version : 1.0.0
# License : MIT
# =============================================================================
#
# WHAT THIS DOES
#   Computes a SHA-256 hash of each document before calling the embedding API.
#   If the hash already exists in the cache, the stored vector is returned
#   and no API call is made. Only new or changed documents are embedded.
#
# EMBEDDING PROVIDER NOTE
#   The Anthropic API does not provide native embeddings. Anthropic recommends
#   Voyage AI. See: https://docs.anthropic.com/en/docs/build-with-claude/embeddings
#   Swap voyageai.Client() for your preferred provider if needed.
#
# PRODUCTION NOTE
#   The in-memory dict here is for demonstration only. In production, replace
#   cache_get() and cache_set() with lookups against your vector database
#   metadata store (pgvector, Pinecone, Weaviate, etc.). Store the content_hash
#   as a metadata field alongside the vector and query for it before re-embedding.
#
# USAGE
#   export VOYAGE_API_KEY=your_key_here
#   python -m token_cost_anatomy.embedding_cache
#
# PREREQUISITES
#   pip install voyageai
# =============================================================================

import hashlib
import os
import voyageai


# ---------------------------------------------------------------------------
# In-memory cache - replace with your vector DB metadata store in production
# Key   : SHA-256 hex digest of the document text
# Value : embedding vector (list of floats)
# ---------------------------------------------------------------------------
_cache: dict[str, list[float]] = {}


def cache_get(content_hash: str) -> list[float] | None:
    """Return cached vector or None if not present."""
    return _cache.get(content_hash)


def cache_set(content_hash: str, vector: list[float]) -> None:
    """Store a vector under its content hash."""
    _cache[content_hash] = vector


def get_embedding_with_cache(
    text: str,
    model: str = "voyage-3",
) -> tuple[list[float], bool]:
    """
    Returns the embedding for text, using the cache when possible.

    Args:
        text:  Text to embed.
        model: Voyage AI model to use.

    Returns:
        (vector, cache_hit) - cache_hit is True when no API call was made.
    """
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    cached = cache_get(content_hash)
    if cached is not None:
        return cached, True

    client = voyageai.Client(api_key=os.environ.get("VOYAGE_API_KEY"))
    response = client.embed([text], model=model)
    vector = response.embeddings[0]

    cache_set(content_hash, vector)
    return vector, False


def embed_corpus(
    documents: list[str],
    model: str = "voyage-3",
) -> dict:
    """
    Embeds a list of documents, skipping any already in cache.

    Args:
        documents: Text strings to embed.
        model:     Voyage AI model to use.

    Returns:
        Dict with vectors, cache_hits count, and api_calls count.
    """
    vectors, hits, misses = [], 0, 0

    for doc in documents:
        vector, from_cache = get_embedding_with_cache(doc, model=model)
        vectors.append(vector)
        if from_cache:
            hits += 1
        else:
            misses += 1

    print(f"Corpus: {len(documents)} docs | {hits} cache hits | {misses} API calls")
    return {"vectors": vectors, "cache_hits": hits, "api_calls": misses}


if __name__ == "__main__":
    docs = [
        "Azure VM Standard_D8s_v3 running at 3% avg CPU, 24/7.",
        "Premium SSD P30 disk unattached for 47 days.",
        "Azure OpenAI endpoint with zero requests in 14 days.",
    ]

    print("First pass (all misses - API calls made):")
    embed_corpus(docs)

    print("\nSecond pass (all hits - no API calls):")
    embed_corpus(docs)

    print("\nThird pass with one new doc (one miss, two hits):")
    embed_corpus(docs + ["Storage account with public blob access enabled."])
