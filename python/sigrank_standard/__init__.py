"""
sigrank-standard — Python implementation of the SigRank Standard v0.1-draft.

The portable five-metric core for AI operator token-processing efficiency.
No dependencies. Conforms to the sigrank/0.1-draft specification.

Metrics:
    Yield      = (cache_read * output) / input^2
    Leverage   = cache_read / input
    Velocity   = output / input
    SNR        = output / (input + output)
    10xDEV     = log10(cache_read / input)

Null semantics:
    - When a denominator is zero, the metric is None (not 0 or Infinity).
    - When cache_read is None, Yield, Leverage, and 10xDEV are None.
    - When cache_write is None, 10xDEV is None.
"""

from .metrics import compute_metrics, build_record
from .conformance import run_conformance, ConformanceResult

__version__ = "0.1.0"
__spec__ = "sigrank/0.1-draft"
__all__ = [
    "compute_metrics",
    "build_record",
    "run_conformance",
    "ConformanceResult",
    "__version__",
    "__spec__",
]
