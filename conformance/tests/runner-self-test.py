#!/usr/bin/env python3
"""
conformance/tests/runner-self-test.py — Self-test for the Python conformance runner.

Mirrors conformance/tests/runner-self-test.mjs. Verifies that the Python
conformance runner correctly REJECTS non-conforming implementations.

This is a meta-test: it ensures the Python conformance suite itself has teeth.
Without it, a regression making the runner always-pass would go undetected.

Usage:
    python3 conformance/tests/runner-self-test.py

Exit code 0 = all self-tests pass. Exit code 1 = a self-test failed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "examples" / "fixtures"

passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✓ {name}")
        passed += 1
    except AssertionError as err:
        print(f"  ✗ {name}")
        print(f"      {err}")
        failed += 1


# ─── Test 1: Runner exits 0 on current fixtures ──────────────────────────────

def test_runner_passes_current_fixtures():
    result = subprocess.run(
        [sys.executable, "-m", "sigrank_standard"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"Runner exited {result.returncode}: {result.stderr}"
    assert "passed, 0 failed" in result.stdout or "ALL PASS" in result.stdout, (
        f"Expected all passed, 0 failed. Got: {result.stdout.strip().splitlines()[-1] if result.stdout.strip() else '(empty)'}"
    )


# ─── Test 2: Runner catches a broken metric implementation ───────────────────
# We temporarily swap a fixture's expected metric to a wrong value and verify
# the runner reports a failure.

def test_runner_catches_incorrect_metric_values():
    fixture_path = FIXTURES_DIR / "01-canonical-reference.json"
    original = fixture_path.read_text()
    modified = json.loads(original)
    modified["expected"]["metrics"]["yield"] = 99999.99  # wrong value

    tmp_dir = Path(tempfile.mkdtemp(prefix="sigrank-self-test-"))
    try:
        tmp_fixtures = tmp_dir / "fixtures"
        tmp_fixtures.mkdir()
        for f in sorted(FIXTURES_DIR.glob("*.json")):
            content = (
                json.dumps(modified, indent=2)
                if f.name == "01-canonical-reference.json"
                else f.read_text()
            )
            (tmp_fixtures / f.name).write_text(content)

        # Run the runner against the temp fixtures dir via the public API
        sys.path.insert(0, str(REPO_ROOT / "python"))
        try:
            from sigrank_standard.conformance import run_conformance
            result = run_conformance(fixtures_dir=tmp_fixtures)
            assert result.failed >= 1, (
                "Runner incorrectly passed with wrong metric value "
                f"(passed={result.passed}, failed={result.failed})"
            )
            assert any("metric yield" in f for f in result.failures), (
                f"Runner did not report the metric failure: {result.failures}"
            )
        finally:
            sys.path.pop(0)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─── Test 3: Runner validates warnings (fixtures with expected warnings exist) ─

def test_runner_validates_warnings():
    files = sorted(FIXTURES_DIR.glob("*.json"))
    fixtures_with_warnings = 0
    for f in files:
        fixture = json.loads(f.read_text())
        warnings = fixture.get("expected", {}).get("warnings")
        if warnings is not None and len(warnings) > 0:
            fixtures_with_warnings += 1
    assert fixtures_with_warnings >= 6, (
        f"Expected at least 6 fixtures with expected warnings, found {fixtures_with_warnings}"
    )


# ─── Test 4: Runner catches missing required_fields ───────────────────────────
# Verify the runner would fail if a fixture required a field the record doesn't
# have. This guards the parity fix for the required_fields validation gap.

def test_runner_catches_missing_required_fields():
    sys.path.insert(0, str(REPO_ROOT / "python"))
    try:
        from sigrank_standard.conformance import _validate_fixture, _find_schema_path
        with open(_find_schema_path()) as f:
            schema = json.load(f)
        fixture = {
            "id": "self-test-required",
            "input": {
                "telemetry": {"input": 1000, "output": 5000, "cache_write": 500, "cache_read": 3000},
                "source": {"provider": "test", "model": "test", "tool": "test"},
            },
            "expected": {
                "metrics": {"yield": 15.0, "leverage": 3.0, "velocity": 5.0, "snr": 0.8333, "dev10x": 0.48},
                "required_fields": ["spec", "timestamp", "source", "telemetry", "metrics", "NONEXISTENT_FIELD"],
            },
        }
        errors = _validate_fixture(fixture, schema)
        assert any("NONEXISTENT_FIELD" in e for e in errors), (
            f"Runner did not catch missing NONEXISTENT_FIELD: {errors}"
        )
    finally:
        sys.path.pop(0)


# ─── Test 5: Runner catches wrong version declaration ────────────────────────

def test_runner_catches_wrong_version():
    sys.path.insert(0, str(REPO_ROOT / "python"))
    try:
        from sigrank_standard.conformance import _validate_fixture, _find_schema_path
        with open(_find_schema_path()) as f:
            schema = json.load(f)
        fixture = {
            "id": "self-test-version",
            "input": {
                "telemetry": {"input": 1000, "output": 5000, "cache_write": 500, "cache_read": 3000},
                "source": {"provider": "test", "model": "test", "tool": "test"},
            },
            "expected": {
                "spec": "sigrank/0.2-draft",
            },
        }
        errors = _validate_fixture(fixture, schema)
        assert any("version declaration" in e for e in errors), (
            f"Runner did not catch wrong spec version: {errors}"
        )
    finally:
        sys.path.pop(0)


# ─── Test 6: Runner catches alias translation leak ───────────────────────────

def test_runner_catches_alias_leak():
    sys.path.insert(0, str(REPO_ROOT / "python"))
    try:
        from sigrank_standard.conformance import _validate_fixture, _find_schema_path
        with open(_find_schema_path()) as f:
            schema = json.load(f)
        fixture = {
            "id": "self-test-alias",
            "input": {
                "telemetry": {"input": 1000, "output": 5000, "cache_creation": 500, "cache_read": 3000},
                "source": {"provider": "test", "model": "test", "tool": "test"},
            },
            "expected": {
                "metrics": {"yield": 15.0, "leverage": 3.0, "velocity": 5.0, "snr": 0.8333, "dev10x": 0.48},
                "output_telemetry_keys": ["input", "output", "cache_write", "cache_read", "LEAKED_KEY"],
            },
        }
        errors = _validate_fixture(fixture, schema)
        assert any("alias translation" in e for e in errors), (
            f"Runner did not catch alias leak: {errors}"
        )
    finally:
        sys.path.pop(0)


# ─── Run all tests ────────────────────────────────────────────────────────────

test("runner exits 0 on current fixtures", test_runner_passes_current_fixtures)
test("runner catches incorrect metric values", test_runner_catches_incorrect_metric_values)
test("runner validates warnings (fixtures with expected warnings exist)", test_runner_validates_warnings)
test("runner catches missing required_fields", test_runner_catches_missing_required_fields)
test("runner catches wrong version declaration", test_runner_catches_wrong_version)
test("runner catches alias translation leak", test_runner_catches_alias_leak)

print()
print(f"Self-test results: {passed} passed, {failed} failed, {passed + failed} total")

if failed > 0:
    sys.exit(1)
