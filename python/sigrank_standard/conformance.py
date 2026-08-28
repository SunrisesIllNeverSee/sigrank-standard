"""
Conformance runner for SigRank Standard v0.1-draft.

Loads JSON fixtures from the examples/fixtures/ directory, computes metrics
using the reference implementation, and validates against expected output.

Usage:
    from sigrank_standard import run_conformance
    result = run_conformance()
    print(f"{result.passed}/{result.total} passed")
"""

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .metrics import compute_metrics


@dataclass
class ConformanceResult:
    """Result of running the conformance suite."""
    passed: int = 0
    failed: int = 0
    total: int = 0
    failures: List[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


def _approx_equal(a, b, tolerance=0.001) -> bool:
    """Compare two values, treating None as equal to None."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < tolerance


def _find_fixtures_dir() -> Path:
    """Find the fixtures directory relative to the package or repo root."""
    # Try relative to this file (python/sigrank_standard/conformance.py)
    # → ../../examples/fixtures/
    here = Path(__file__).parent
    candidates = [
        here.parent.parent / "examples" / "fixtures",
        here.parent / "examples" / "fixtures",
        Path.cwd() / "examples" / "fixtures",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    raise FileNotFoundError(
        "Could not find examples/fixtures/ directory. "
        "Run from the sigrank-standard repo root or install with fixtures."
    )


def _validate_fixture(fixture: dict) -> List[str]:
    """Validate a single fixture. Returns list of error strings (empty = pass)."""
    errors = []
    fixture_id = fixture.get("id", "unknown")

    telemetry = fixture.get("input", {}).get("telemetry", {})
    expected = fixture.get("expected", {})

    # Schema validity — input and output are required
    if telemetry.get("input") is None:
        errors.append(f"{fixture_id}: schema: input is required")
    if telemetry.get("output") is None:
        errors.append(f"{fixture_id}: schema: output is required")

    # Compute metrics
    result = compute_metrics(
        input_tokens=telemetry.get("input", 0),
        output_tokens=telemetry.get("output", 0),
        cache_write=telemetry.get("cache_write", telemetry.get("cache_creation")),
        cache_read=telemetry.get("cache_read"),
    )

    # Metric comparison
    expected_metrics = expected.get("metrics", {})
    for key, expected_value in expected_metrics.items():
        actual_value = result["metrics"].get(key)
        if not _approx_equal(actual_value, expected_value):
            errors.append(
                f"{fixture_id}: metric {key}: expected {expected_value}, got {actual_value}"
            )

    # Extension exclusion — no forbidden metrics in output
    for forbidden in expected.get("forbidden_metrics", []):
        if forbidden in result["metrics"]:
            errors.append(f"{fixture_id}: extension leak: {forbidden} found in metrics")

    # Required metrics present
    for required in expected.get("required_metrics", []):
        if required not in result["metrics"]:
            errors.append(f"{fixture_id}: missing required metric: {required}")

    # Content independence — no forbidden fields in telemetry
    for forbidden in expected.get("forbidden_fields", []):
        if forbidden in telemetry:
            errors.append(f"{fixture_id}: content leak: {forbidden} found in telemetry")

    return errors


def run_conformance(fixtures_dir: Path = None) -> ConformanceResult:
    """
    Run the full conformance suite against all JSON fixtures.

    Args:
        fixtures_dir: Path to the fixtures directory. If None, auto-discovers.

    Returns:
        ConformanceResult with pass/fail counts and failure details.
    """
    if fixtures_dir is None:
        fixtures_dir = _find_fixtures_dir()

    fixture_files = sorted(fixtures_dir.glob("*.json"))
    result = ConformanceResult(total=len(fixture_files))

    for fixture_path in fixture_files:
        with open(fixture_path) as f:
            fixture = json.load(f)

        errors = _validate_fixture(fixture)
        if errors:
            result.failed += 1
            result.failures.extend(errors)
        else:
            result.passed += 1

    return result


def main():
    """CLI entry point for the conformance runner."""
    result = run_conformance()
    print(f"SigRank Standard v0.1-draft Conformance Suite (Python)")
    print(f"{result.total} fixtures loaded")
    print()
    if result.all_passed:
        print(f"Results: {result.passed}/{result.total} passed — ALL PASS")
    else:
        print(f"Results: {result.passed}/{result.total} passed, {result.failed} FAILED")
        for failure in result.failures:
            print(f"  {failure}")
    return 0 if result.all_passed else 1
