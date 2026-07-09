# =============================================================================
# test_offline.py
# Offline unit tests - no API key required, no live calls made.
#
# Project : Token Cost Anatomy
# Author  : Shannon Eldridge-Kuehn
# Blog    : https://shankuehn.io
# Created : 2026-07-09
# Version : 1.0.0
# License : MIT
# =============================================================================
#
# USAGE
#   cd token-cost-anatomy
#   pytest tests/test_offline.py -v
# =============================================================================

import sys
import os
import hashlib
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from token_cost_anatomy.pricing import cost_of, MODEL_COSTS
from token_cost_anatomy.tracked_call import CallRecord, summarize_costs


# ---------------------------------------------------------------------------
# pricing.py tests
# ---------------------------------------------------------------------------

class TestCostOf:
    def test_zero_tokens_returns_zero(self):
        result = cost_of("claude-sonnet-4-6")
        assert result == 0.0

    def test_input_only(self):
        result = cost_of("claude-sonnet-4-6", input_tokens=1_000_000)
        assert result == 3.00

    def test_output_only(self):
        result = cost_of("claude-sonnet-4-6", output_tokens=1_000_000)
        assert result == 15.00

    def test_cache_read_cheaper_than_input(self):
        fresh = cost_of("claude-sonnet-4-6", input_tokens=1_000_000)
        cached = cost_of("claude-sonnet-4-6", cache_read_tokens=1_000_000)
        assert cached < fresh
        assert cached == pytest.approx(fresh * 0.10, rel=1e-3)

    def test_unknown_model_raises(self):
        import pytest
        with pytest.raises(KeyError):
            cost_of("gpt-not-a-real-model", input_tokens=1000)

    def test_haiku_cheaper_than_sonnet(self):
        sonnet = cost_of("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000)
        haiku  = cost_of("claude-haiku-4-5",  input_tokens=1_000_000, output_tokens=1_000_000)
        assert haiku < sonnet

    def test_all_models_in_price_book(self):
        for model in MODEL_COSTS:
            result = cost_of(model, input_tokens=100, output_tokens=100)
            assert result >= 0.0


# ---------------------------------------------------------------------------
# tracked_call.py tests (no live API calls)
# ---------------------------------------------------------------------------

import pytest
import time

def make_record(**kwargs) -> CallRecord:
    defaults = dict(
        timestamp=time.time(),
        model="claude-sonnet-4-6",
        team="test-team",
        use_case="test-use-case",
        input_tokens=1000,
        output_tokens=500,
        cache_read_tokens=0,
        cache_write_tokens=0,
        estimated_cost_usd=0.0105,
        latency_ms=320.0,
    )
    defaults.update(kwargs)
    return CallRecord(**defaults)


class TestSummarizeCosts:
    def test_empty_log_returns_zero(self):
        result = summarize_costs([])
        assert result["total_usd"] == 0.0
        assert result["by_team"] == {}

    def test_single_record(self):
        record = make_record(team="alpha", use_case="search", estimated_cost_usd=0.05)
        result = summarize_costs([record])
        assert result["total_usd"] == pytest.approx(0.05)
        assert "alpha" in result["by_team"]
        assert result["by_team"]["alpha"]["total_usd"] == pytest.approx(0.05)

    def test_multiple_teams(self):
        records = [
            make_record(team="alpha", estimated_cost_usd=0.10),
            make_record(team="beta",  estimated_cost_usd=0.05),
            make_record(team="alpha", estimated_cost_usd=0.10),
        ]
        result = summarize_costs(records)
        assert result["total_usd"] == pytest.approx(0.25)
        assert result["by_team"]["alpha"]["total_usd"] == pytest.approx(0.20)
        assert result["by_team"]["beta"]["total_usd"]  == pytest.approx(0.05)

    def test_use_case_call_count(self):
        records = [
            make_record(team="alpha", use_case="extract", estimated_cost_usd=0.01),
            make_record(team="alpha", use_case="extract", estimated_cost_usd=0.01),
            make_record(team="alpha", use_case="summary", estimated_cost_usd=0.005),
        ]
        result = summarize_costs(records)
        uc = result["by_team"]["alpha"]["by_use_case"]
        assert uc["extract"]["calls"] == 2
        assert uc["summary"]["calls"] == 1


# ---------------------------------------------------------------------------
# embedding_cache.py tests (no live API calls)
# ---------------------------------------------------------------------------

class TestEmbeddingCache:
    def test_same_text_same_hash(self):
        text = "Azure VM Standard_D8s_v3"
        h1 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        h2 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert h1 == h2

    def test_different_text_different_hash(self):
        h1 = hashlib.sha256("text A".encode()).hexdigest()
        h2 = hashlib.sha256("text B".encode()).hexdigest()
        assert h1 != h2

    def test_cache_hit_skips_api(self):
        from token_cost_anatomy.embedding_cache import _cache, cache_set, get_embedding_with_cache

        fake_vector = [0.1, 0.2, 0.3]
        text = "This text is already cached"
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_set(content_hash, fake_vector)

        with patch("voyageai.Client") as mock_client:
            vector, from_cache = get_embedding_with_cache(text)
            mock_client.assert_not_called()

        assert from_cache is True
        assert vector == fake_vector
