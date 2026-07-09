# =============================================================================
# pricing.py
# Single source of truth for Anthropic token pricing.
#
# Project : Token Cost Anatomy
# Author  : Shannon Eldridge-Kuehn
# Blog    : https://shankuehn.io
# Created : 2026-07-09
# Version : 1.0.0
# License : MIT
# =============================================================================
#
# WHAT THIS IS
#   A centralized price book for Anthropic Claude models. Import it into any
#   module that needs to estimate call cost rather than hard-coding numbers
#   in multiple places.
#
# KEEP IT FRESH
#   These prices change. Verify before using for budgeting or chargeback:
#   https://www.anthropic.com/pricing
#
# UNITS
#   All costs are USD per 1,000,000 tokens (per MTok).
#
# HOW ANTHROPIC BILLS CACHE TOKENS
#   input_tokens       fresh (non-cached) input - billed at input rate
#   cache_write_tokens written to cache          - billed at 1.25x input (5-min TTL)
#                                                  or 2x input (1-hour TTL)
#   cache_read_tokens  served from cache         - billed at 0.10x input (90% savings)
#   output_tokens      generated completion      - billed at output rate
# =============================================================================

PRICING_VERIFIED = "2026-07"

# USD per 1,000,000 tokens
MODEL_COSTS: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input":         3.00,
        "output":       15.00,
        "cache_write":   3.75,   # 5-minute TTL (1.25x input)
        "cache_write_1h": 6.00,  # 1-hour TTL  (2x input)
        "cache_read":    0.30,   # 0.10x input
    },
    "claude-haiku-4-5": {
        "input":         1.00,
        "output":        5.00,
        "cache_write":   1.25,
        "cache_write_1h": 2.00,
        "cache_read":    0.10,
    },
}


def cost_of(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """
    Estimate the USD cost of a single Anthropic API call.

    Args:
        model:              Anthropic model ID string.
        input_tokens:       Fresh (non-cached) input tokens from response.usage.
        output_tokens:      Output tokens from response.usage.
        cache_read_tokens:  Tokens served from cache (response.usage.cache_read_input_tokens).
        cache_write_tokens: Tokens written to cache (response.usage.cache_creation_input_tokens).

    Returns:
        Estimated cost in USD as a float.

    Raises:
        KeyError: If the model is not in the price book. Add it to MODEL_COSTS.
    """
    if model not in MODEL_COSTS:
        raise KeyError(
            f"Model '{model}' not in price book. "
            f"Add it to pricing.py or verify the model ID. "
            f"Known models: {list(MODEL_COSTS.keys())}"
        )

    prices = MODEL_COSTS[model]
    return (
        (input_tokens        / 1_000_000) * prices["input"]
        + (output_tokens     / 1_000_000) * prices["output"]
        + (cache_read_tokens / 1_000_000) * prices["cache_read"]
        + (cache_write_tokens/ 1_000_000) * prices["cache_write"]
    )
