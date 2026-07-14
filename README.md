# token-cost-anatomy

> Companion code for **Token Cost Anatomy: The Five-Headed Bill Nobody Budgeted For**
> Published on [Cloudy Musings](https://shankuehn.io) by Shannon Eldridge-Kuehn

Python utilities for understanding, attributing, and optimizing AI token spend
with the Anthropic Claude API. Built for FinOps practitioners who want actionable
cost controls, not just dashboards.

---

## Contents

```
token-cost-anatomy/
├── src/
│   └── ├── pricing.py           # Centralized price book and cost_of() helper
│       ├── prompt_caching.py    # Input token optimization via prefix caching
│       ├── structured_output.py # Output token optimization via JSON schema
│       ├── embedding_cache.py   # Embedding token optimization via content hashing
│       └── tracked_call.py      # Cost attribution wrapper - chargeback foundation
├── examples/
│   └── example_pipeline.py      # End-to-end pipeline combining all modules
├── tests/
│   └── test_offline.py          # Offline unit tests - no API key required
├── docs/
│   └── fine-tuning-and-infra.md # Notes on fine-tuning and inference infra buckets
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## The Five Token Buckets

| # | Token Type | Typical % | Module |
|---|------------|-----------|--------|
| 1 | Input tokens | 38% | `prompt_caching.py` |
| 2 | Output tokens | 28% | `structured_output.py` |
| 3 | Embedding tokens | 12% | `embedding_cache.py` |
| 4 | Fine-tuning tokens | 12% | `docs/fine-tuning-and-infra.md` |
| 5 | Inference infrastructure | 10% | `docs/fine-tuning-and-infra.md` |

Percentages are illustrative composites from FinOps Foundation AI/ML Working Group
data. Your actual mix depends on your workload.

---

## Prerequisites

- Python 3.11 or later
- [Anthropic API key](https://console.anthropic.com/) (for all modules except embedding)
- [Voyage AI API key](https://www.voyageai.com/) (for `embedding_cache.py` only)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/token-cost-anatomy.git
cd token-cost-anatomy

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API keys
export ANTHROPIC_API_KEY=your_anthropic_key_here
export VOYAGE_API_KEY=your_voyage_key_here     # only needed for embedding_cache.py
```

---

## Running the Tests (no API key required)

```bash
pytest tests/test_offline.py -v
```

All tests run fully offline. They verify pricing math, cost aggregation, and
embedding cache hit logic without making any API calls.

---

## Usage

### End-to-end example pipeline

```bash
python examples/example_pipeline.py
```

Simulates a nightly cost governance job across two mock subscriptions. It
combines structured signal extraction, executive summary generation via a
cheaper model, and cost attribution logging. Replace the mock payloads with
live calls to Azure Resource Graph, AWS Cost Explorer, or GCP Asset Inventory.

---

### pricing.py - centralized cost helper

Used internally by `tracked_call.py`. Import directly if you need to estimate
cost outside of a wrapped call.

```python
from token_cost_anatomy.pricing import cost_of

# Estimate cost of a single call
usd = cost_of(
    "claude-sonnet-4-6",
    input_tokens=1200,
    output_tokens=350,
    cache_read_tokens=8000,
)
print(f"Estimated cost: ${usd:.6f}")
```

Update `MODEL_COSTS` in `pricing.py` when Anthropic publishes new rates:
https://www.anthropic.com/pricing

---

### prompt_caching.py - input token optimization

```bash
python -m token_cost_anatomy.prompt_caching
```

```python
from token_cost_anatomy.prompt_caching import call_with_cache

result = call_with_cache("Analyze cost anomalies for sub-prod-1234.")
```

**How it works:**
Cache reads cost $0.30/M tokens versus $3.00/M for fresh input (90% reduction).
The first call writes the cache at 1.25x the normal input rate. The break-even
is two calls. Every call after that is savings.

**Cache TTL:**
Default is 5 minutes (`"type": "ephemeral"`). Set `"type": "persistent"` in
`cache_control` for a 1-hour TTL, billed at 2x input on write.

**When it won't help:**
Low-volume or highly variable prompts where the cache expires between calls.
Profile your call frequency before enabling.

---

### structured_output.py - output token optimization

```bash
python -m token_cost_anatomy.structured_output
```

```python
from token_cost_anatomy.structured_output import extract_cost_signals

signal = extract_cost_signals(resource_data_string)
print(signal.severity)                         # "high"
print(f"${signal.estimated_monthly_waste_usd:,.2f}")
```

**How it works:**
Constrains output by asking for a compact JSON schema instead of narrative prose.
Reducing average output from 2,000 to 800 tokens saves $0.003 per call. At
10M calls/month that is $30K annually from a two-hour change.

**Tuning `max_tokens`:**
Set it to the realistic maximum size your schema can produce. Too low truncates
the response mid-JSON. Too high wastes budget headroom.

---

### embedding_cache.py - embedding token optimization

```bash
python -m token_cost_anatomy.embedding_cache
```

```python
from token_cost_anatomy.embedding_cache import get_embedding_with_cache

vector, from_cache = get_embedding_with_cache("Your document text here.")
if from_cache:
    print("Cache hit - no API call made.")
```

**Embedding provider:**
The Anthropic API does not provide native embeddings. This module uses
[Voyage AI](https://www.voyageai.com/), which Anthropic recommends:
https://docs.anthropic.com/en/docs/build-with-claude/embeddings

**Production swap:**
The in-memory `_cache` dict is for demonstration. In production, replace
`cache_get()` and `cache_set()` with lookups against your vector database.
Store the content hash as a metadata field alongside each vector and query
for it before deciding to re-embed.

Compatible vector databases:
- [pgvector](https://github.com/pgvector/pgvector) (self-hosted Postgres)
- [Pinecone](https://www.pinecone.io/)
- [Weaviate](https://weaviate.io/)

---

### tracked_call.py - cost attribution

```bash
python -m token_cost_anatomy.tracked_call
```

```python
from token_cost_anatomy.tracked_call import tracked_call, summarize_costs

result = tracked_call(
    messages=[{"role": "user", "content": "Summarize this cost report..."}],
    team="platform-engineering",
    use_case="cost-anomaly-detection",
)

# After a batch of calls:
summary = summarize_costs()
print(summary)
```

**Wiring into OpenTelemetry:**
Replace the `emit()` function in `tracked_call.py` with your preferred sink.
A commented OTel example is included at the top of the file.

**FinOps maturity path** (per FinOps Foundation token economics working group):
1. API key governance - one key per team, know who owns what
2. Observability (`tracked_call.py`) - log cost and attribution per call
3. Model right-sizing - route cheaper models where quality allows
4. Chargeback / showback - bill teams from call_log data

---

## Model Right-Sizing

Most workloads do not require the frontier model. Route extraction, classification,
and summary tasks to Haiku and reserve Sonnet for complex reasoning.

| Model | Input | Output | Best For |
|-------|-------|--------|----------|
| claude-sonnet-4-6 | $3.00/M | $15.00/M | Complex reasoning, synthesis |
| claude-haiku-4-5 | $1.00/M | $5.00/M | Classification, extraction, summaries |

Routing simple tasks to Haiku cuts per-call cost by 67% with minimal quality
impact. The example pipeline demonstrates this pattern: Sonnet for signal
extraction, Haiku for the executive summary.

Verify current pricing: https://www.anthropic.com/pricing

---

## Additional Resources

- [FinOps Foundation: FinOps for AI](https://www.finops.org/wg/finops-for-ai-overview/)
- [FinOps Foundation: Token Economics SaaS](https://www.finops.org/wg/token-economics-saas/)
- [FinOps Foundation: Cost Estimation of AI Workloads](https://www.finops.org/wg/cost-estimation-of-ai-workloads/)
- [Anthropic: Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Anthropic: Embeddings](https://docs.anthropic.com/en/docs/build-with-claude/embeddings)
- [Anthropic: Pricing](https://www.anthropic.com/pricing)
- [LLMLingua: Prompt Compression](https://github.com/microsoft/LLMLingua)
- [Hugging Face PEFT: LoRA Adapters](https://huggingface.co/docs/peft/en/index)

---

## Author

**Shannon Eldridge-Kuehn**
Principal Solutions Engineer at [AHEAD](https://www.ahead.com)
Blog: [Cloudy Musings](https://shankuehn.io)

---

## License

MIT. See [LICENSE](LICENSE) for details.
