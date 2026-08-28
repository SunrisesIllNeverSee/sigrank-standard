# sigrank-standard (Python)

Portable five-metric core for AI operator token-processing efficiency.

## Install

```bash
pip install sigrank-standard
```

## Usage

### Compute metrics

```python
from sigrank_standard import compute_metrics, build_record

# Four token pillars: input, output, cache_write, cache_read
result = compute_metrics(
    input_tokens=1_251_211,
    output_tokens=11_296_121,
    cache_write=128_196_310,
    cache_read=2_555_179_769,
)
print(result["metrics"])
# {'yield': 18436.98, 'leverage': 2042.2, 'velocity': 9.028, 'snr': 0.9, 'dev10x': 3.31}
```

### Build a full record

```python
from sigrank_standard import build_record
import json

record = build_record(
    input_tokens=1_251_211,
    output_tokens=11_296_121,
    cache_write=128_196_310,
    cache_read=2_555_179_769,
    provider="anthropic",
    model="claude-sonnet-4",
    tool="claude-code",
)
print(json.dumps(record, indent=2))
```

### Run conformance suite

```bash
sigrank-conformance
# or
python -m sigrank_standard
```

## Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Yield (Υ) | `(cache_read * output) / input^2` | Token cascade efficiency |
| Leverage | `cache_read / input` | Context reuse |
| Velocity | `output / input` | Output amplification |
| SNR | `output / (input + output)` | Signal cleanliness |
| 10xDEV | `log10(cache_read / input)` | Dev leverage |

## Null semantics

- When a denominator is zero, the metric is `None` (not 0 or Infinity)
- When `cache_read` is `None`, Yield, Leverage, and 10xDEV are `None`
- When `cache_write` is `None`, 10xDEV is `None`

## Spec

SigRank Standard v0.1-draft. See [signalaf.com/standard](https://signalaf.com/standard).

## License

Apache-2.0
