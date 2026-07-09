# =============================================================================
# prompt_caching.py
# Demonstrates Anthropic prefix caching to reduce input token costs by up to 90%.
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
#   Wraps Anthropic API calls so a large, stable system prompt is cached
#   between calls. On the first call Anthropic writes the cache (billed at
#   1.25x input rate). On subsequent calls within the TTL window, reads are
#   90% cheaper than fresh input tokens.
#
# WHEN TO USE IT
#   - Applications with a large, stable system prompt called repeatedly
#   - RAG pipelines where context documents don't change between calls
#   - Multi-step agentic workflows passing the same context window across hops
#
# WHEN IT WON'T HELP
#   - Low-volume or highly variable prompts where the cache expires between calls
#   - Cache TTL is 5 minutes by default. Use type="persistent" for 1-hour TTL
#     (billed at 2x input on write, still 0.10x on read)
#
# USAGE
#   export ANTHROPIC_API_KEY=your_key_here
#   python -m token_cost_anatomy.prompt_caching
#
# COST REFERENCE (https://www.anthropic.com/pricing)
#   claude-sonnet-4-6  fresh input:  $3.00 / 1M tokens
#   claude-sonnet-4-6  cache read:   $0.30 / 1M tokens  (90% reduction)
#   claude-sonnet-4-6  cache write:  $3.75 / 1M tokens  (one-time per TTL window)
# =============================================================================

import os
import anthropic


SYSTEM_PROMPT = """
You are a cloud cost governance assistant. Your job is to analyze
Azure Resource Graph query results and identify cost anomalies,
security posture gaps, and compliance drift across subscriptions.

When analyzing cost data:
- Flag resources with no cost allocation tags
- Highlight idle or underutilized resources
- Call out spend that exceeds 20% month-over-month growth
- Prioritize findings by estimated monthly waste in USD

[Extend this block with your domain-specific instructions.
The longer and more stable it is, the more cache savings you get.]
"""


def call_with_cache(
    user_message: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
) -> str:
    """
    Makes an Anthropic API call with prefix caching on the system prompt.

    On the first call, Anthropic writes the cache (billed at 1.25x input rate).
    On subsequent calls within the 5-minute TTL, reads are billed at 0.10x input.
    Break-even: two API calls. Everything after is savings.

    Args:
        user_message: The user query or data payload.
        model:        The Anthropic model to use.
        max_tokens:   Hard ceiling on output tokens.

    Returns:
        The model's text response.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # that's the whole trick
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    usage = response.usage
    cache_read  = getattr(usage, "cache_read_input_tokens", 0)
    cache_write = getattr(usage, "cache_creation_input_tokens", 0)

    print("--- Cache Usage ---")
    print(f"  Fresh input : {usage.input_tokens}")
    print(f"  Cache write : {cache_write}  (1.25x rate, one-time per TTL window)")
    print(f"  Cache read  : {cache_read}   (0.10x rate, 90% savings)")
    print(f"  Output      : {usage.output_tokens}")
    print("-------------------")

    return response.content[0].text


if __name__ == "__main__":
    print("Call 1 - expect cache_write > 0, cache_read = 0:")
    call_with_cache("Summarize cost anomalies for subscription sub-1234 this month.")
    print()
    print("Call 2 - expect cache_read > 0, cache_write = 0:")
    call_with_cache("Which idle resources should we prioritize for shutdown?")
