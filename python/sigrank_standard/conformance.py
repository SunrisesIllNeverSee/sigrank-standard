"""
Conformance runner for SigRank Standard v0.1-draft.

Loads JSON fixtures from the examples/fixtures/ directory, builds a complete
SigRank Standard record from each fixture input using ``build_record``, and
validates the record against the expected output AND the JSON Schema.

This runner mirrors the authoritative JS runner (``conformance/runner.mjs``)
validation surface byte-for-byte:
  - schema validity (self-contained validator, no external deps)
  - exact primitive semantics (non-negative integers, null for unavailable cache)
  - metric comparison (with tolerance)
  - warning semantics (ordered arrays)
  - version declaration (record.spec against expected.spec)
  - alias translation (output telemetry keys + cache_creation leak check)
  - content independence (forbidden fields in telemetry AND record top-level)
  - required fields (record top-level)
  - extension exclusion (forbidden metrics)
  - required metrics (all five present)
  - provenance (non-empty provider, model, tool strings)

Usage:
    from sigrank_standard import run_conformance
    result = run_conformance()
    print(f"{result.passed}/{result.total} passed")
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from .metrics import build_record


SPEC_VERSION = "sigrank/0.1-draft"


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


def _approx_equal(a, b, tolerance: float = 0.001) -> bool:
    """Compare two values, treating None as equal to None."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < tolerance


def _arrays_equal(a, b) -> bool:
    """Order-sensitive list equality."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y:
            return False
    return True


def _find_fixtures_dir() -> Path:
    """Find the fixtures directory relative to the package or repo root."""
    # Try relative to this file (python/sigrank_standard/conformance.py)
    # -> ../../examples/fixtures/
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


def _find_schema_path() -> Path:
    """Find the schema file relative to the package or repo root."""
    here = Path(__file__).parent
    candidates = [
        here.parent.parent / "schema" / "sigrank-operator-record-v0.1.schema.json",
        here.parent / "schema" / "sigrank-operator-record-v0.1.schema.json",
        Path.cwd() / "schema" / "sigrank-operator-record-v0.1.schema.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Could not find schema/sigrank-operator-record-v0.1.schema.json. "
        "Run from the sigrank-standard repo root or install with schema."
    )


# ─── Schema validation (self-contained, no external deps) ────────────────────
# Mirrors the JS runner's ``validateAgainstSchema``. Covers the schema features
# used by sigrank-operator-record-v0.1.schema.json:
# type (string or array of types incl. null), required, const,
# additionalProperties, minimum, minLength, enum, items, properties.

def _check_type(value: Any, type_decl, path: str, errors: List[str]) -> None:
    types = type_decl if isinstance(type_decl, list) else [type_decl]
    matched = False
    for t in types:
        if value is None:
            if t == "null":
                matched = True
                break
            continue
        if t == "integer":
            if isinstance(value, int) and not isinstance(value, bool):
                matched = True
                break
        elif t == "number":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                matched = True
                break
        elif t == "string":
            if isinstance(value, str):
                matched = True
                break
        elif t == "object":
            if isinstance(value, dict):
                matched = True
                break
        elif t == "array":
            if isinstance(value, list):
                matched = True
                break
    if not matched:
        errors.append(
            f"schema {path}: expected type {json.dumps(type_decl)}, "
            f"got {type(value).__name__} ({json.dumps(value)})"
        )


def _validate_schema_node(value: Any, node: dict, path: str, errors: List[str]) -> None:
    # const — exact match, short-circuit
    if "const" in node:
        if value != node["const"]:
            errors.append(
                f"schema {path}: expected const {json.dumps(node['const'])}, "
                f"got {json.dumps(value)}"
            )
        return

    # enum
    if "enum" in node:
        if value not in node["enum"]:
            errors.append(
                f"schema {path}: expected one of {json.dumps(node['enum'])}, "
                f"got {json.dumps(value)}"
            )

    # type (string or array of types)
    if "type" in node:
        _check_type(value, node["type"], path, errors)

    # minimum (only for numbers)
    if "minimum" in node and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < node["minimum"]:
            errors.append(f"schema {path}: value {value} below minimum {node['minimum']}")

    # minLength (only for strings)
    if "minLength" in node and isinstance(value, str):
        if len(value) < node["minLength"]:
            errors.append(
                f"schema {path}: string length {len(value)} below minLength {node['minLength']}"
            )

    # required (only for objects)
    if "required" in node and isinstance(value, dict):
        for req in node["required"]:
            if req not in value:
                errors.append(f"schema {path}: missing required field \"{req}\"")

    # additionalProperties: false (only for objects)
    if node.get("additionalProperties") is False and isinstance(value, dict):
        allowed = set((node.get("properties") or {}).keys())
        for key in value.keys():
            if key not in allowed:
                errors.append(f"schema {path}: additional property \"{key}\" not allowed")

    # properties (recurse)
    if "properties" in node and isinstance(value, dict):
        for key, sub_schema in node["properties"].items():
            if key in value:
                _validate_schema_node(value[key], sub_schema, f"{path}.{key}", errors)

    # items (recurse for arrays)
    if "items" in node and isinstance(value, list):
        for i, item in enumerate(value):
            _validate_schema_node(item, node["items"], f"{path}[{i}]", errors)


def _validate_against_schema(record: dict, schema: dict) -> List[str]:
    """Validate a record against the JSON Schema. Returns list of errors."""
    errors: List[str] = []
    _validate_schema_node(record, schema, "record", errors)
    return errors


# ─── Fixture validation ──────────────────────────────────────────────────────

def _validate_fixture(fixture: dict, schema: dict) -> List[str]:
    """Validate a single fixture. Returns list of error strings (empty = pass)."""
    errors: List[str] = []
    fixture_id = fixture.get("id", "unknown")

    telemetry = fixture.get("input", {}).get("telemetry", {})
    source = fixture.get("input", {}).get("source", {})
    expected = fixture.get("expected", {})

    # Build a complete record via build_record so we validate the full output
    # surface (spec, timestamp, source, telemetry, metrics, warnings) — not just
    # the computed metrics. This matches the JS runner's buildRecord path.
    record = build_record(
        input_tokens=telemetry.get("input", 0),
        output_tokens=telemetry.get("output", 0),
        cache_write=telemetry.get("cache_write", telemetry.get("cache_creation")),
        cache_read=telemetry.get("cache_read"),
        provider=source.get("provider", "unknown"),
        model=source.get("model", "unknown"),
        tool=source.get("tool", "unknown"),
    )

    # 1. Schema validity — validate the built record against the JSON Schema
    errors.extend(_validate_against_schema(record, schema))

    # 2. Primitive semantics — required telemetry fields present and non-negative integers
    t = record["telemetry"]
    if not (isinstance(t["input"], int) and not isinstance(t["input"], bool) and t["input"] >= 0):
        errors.append(f"{fixture_id}: primitive: input must be non-negative integer, got {t['input']}")
    if not (isinstance(t["output"], int) and not isinstance(t["output"], bool) and t["output"] >= 0):
        errors.append(f"{fixture_id}: primitive: output must be non-negative integer, got {t['output']}")
    if t["cache_write"] is not None and not (
        isinstance(t["cache_write"], int) and not isinstance(t["cache_write"], bool) and t["cache_write"] >= 0
    ):
        errors.append(f"{fixture_id}: primitive: cache_write must be non-negative integer or null, got {t['cache_write']}")
    if t["cache_read"] is not None and not (
        isinstance(t["cache_read"], int) and not isinstance(t["cache_read"], bool) and t["cache_read"] >= 0
    ):
        errors.append(f"{fixture_id}: primitive: cache_read must be non-negative integer or null, got {t['cache_read']}")

    # 3. Metric comparison — exact values with tolerance
    expected_metrics = expected.get("metrics", {})
    for key, expected_value in expected_metrics.items():
        actual_value = record["metrics"].get(key)
        if not _approx_equal(actual_value, expected_value):
            errors.append(
                f"{fixture_id}: metric {key}: expected {expected_value}, got {actual_value}"
            )

    # 4. Warning semantics — warnings must match expected as ordered arrays
    expected_warnings = expected.get("warnings")
    if expected_warnings is not None:
        if not _arrays_equal(record["warnings"], expected_warnings):
            errors.append(
                f"{fixture_id}: warnings mismatch:\n"
                f"        expected: {expected_warnings}\n"
                f"        actual:   {record['warnings']}"
            )

    # 5. Version declaration — the built record must declare spec: sigrank/0.1-draft
    expected_spec = expected.get("spec")
    if expected_spec is not None:
        if record["spec"] != expected_spec:
            errors.append(
                f"{fixture_id}: version declaration: expected spec \"{expected_spec}\", "
                f"got \"{record['spec']}\""
            )

    # 6. Alias translation — output telemetry must be normalized to cache_write
    #    (not cache_creation). Validate the actual output telemetry keys.
    expected_output_keys = expected.get("output_telemetry_keys")
    if expected_output_keys is not None:
        actual_keys = sorted(record["telemetry"].keys())
        expected_keys_sorted = sorted(expected_output_keys)
        if not _arrays_equal(actual_keys, expected_keys_sorted):
            errors.append(
                f"{fixture_id}: alias translation: expected telemetry keys "
                f"{expected_keys_sorted}, got {actual_keys}"
            )
        if "cache_creation" in record["telemetry"]:
            errors.append(
                f"{fixture_id}: alias translation: cache_creation leaked into output telemetry "
                f"(should be normalized to cache_write)"
            )

    # 7. Content independence — forbidden fields must not appear in telemetry OR record
    forbidden_fields = expected.get("forbidden_fields", [])
    for forbidden in forbidden_fields:
        if forbidden in record["telemetry"]:
            errors.append(f"{fixture_id}: content leak: forbidden field \"{forbidden}\" found in telemetry")
        if forbidden in record:
            errors.append(f"{fixture_id}: content leak: forbidden field \"{forbidden}\" found in record")

    # 8. Required fields — the record must contain all required top-level fields
    required_fields = expected.get("required_fields", [])
    for required in required_fields:
        if required not in record:
            errors.append(f"{fixture_id}: missing required field: \"{required}\" not in record")

    # 9. Extension exclusion — no forbidden metrics in the output
    forbidden_metrics = expected.get("forbidden_metrics", [])
    for forbidden in forbidden_metrics:
        if forbidden in record["metrics"]:
            errors.append(f"{fixture_id}: extension leak: forbidden metric \"{forbidden}\" found in metrics")

    # 10. Required metrics — the five portable metrics must all be present
    required_metrics = expected.get("required_metrics", [])
    for required in required_metrics:
        if required not in record["metrics"]:
            errors.append(f"{fixture_id}: missing required metric: \"{required}\" not in metrics")

    # 11. Provenance — source object must have provider, model, tool (non-empty strings)
    s = record["source"]
    if not s or not isinstance(s.get("provider"), str) or len(s["provider"]) < 1:
        errors.append(f"{fixture_id}: provenance: source.provider must be a non-empty string")
    if not s or not isinstance(s.get("model"), str) or len(s["model"]) < 1:
        errors.append(f"{fixture_id}: provenance: source.model must be a non-empty string")
    if not s or not isinstance(s.get("tool"), str) or len(s["tool"]) < 1:
        errors.append(f"{fixture_id}: provenance: source.tool must be a non-empty string")

    return errors


def run_conformance(fixtures_dir: Optional[Path] = None) -> ConformanceResult:
    """
    Run the full conformance suite against all JSON fixtures.

    Args:
        fixtures_dir: Path to the fixtures directory. If None, auto-discovers.

    Returns:
        ConformanceResult with pass/fail counts and failure details.
    """
    if fixtures_dir is None:
        fixtures_dir = _find_fixtures_dir()

    try:
        schema_path = _find_schema_path()
        with open(schema_path) as f:
            schema = json.load(f)
    except FileNotFoundError:
        # Schema is optional when running from an installed wheel without the
        # repo; skip schema validation but still validate everything else.
        schema = None

    fixture_files = sorted(fixtures_dir.glob("*.json"))
    result = ConformanceResult(total=len(fixture_files))

    for fixture_path in fixture_files:
        with open(fixture_path) as f:
            fixture = json.load(f)

        errors = _validate_fixture(fixture, schema if schema is not None else {})
        if errors:
            result.failed += 1
            result.failures.extend(errors)
        else:
            result.passed += 1

    return result


def main() -> int:
    """CLI entry point for the conformance runner."""
    result = run_conformance()
    print("SigRank Standard v0.1-draft Conformance Suite (Python)")
    print(f"{result.total} fixtures loaded")
    print()
    if result.all_passed:
        print(f"Results: {result.passed}/{result.total} passed — ALL PASS")
    else:
        print(f"Results: {result.passed}/{result.total} passed, {result.failed} FAILED")
        for failure in result.failures:
            print(f"  {failure}")
    return 0 if result.all_passed else 1
