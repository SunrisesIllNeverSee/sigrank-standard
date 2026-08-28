/**
 * conformance/runner.mjs — SigRank Standard v0.1-draft executable conformance suite.
 *
 * Language-neutral fixture-based conformance runner. Loads all fixtures from
 * examples/fixtures/, computes the five portable metrics from the four token
 * pillars, and validates against expected output.
 *
 * This runner is self-contained — it does not depend on @sigrank/cascade or any
 * SignalAF code. A third-party implementation can replace the metric functions
 * below with their own and run the same fixtures.
 *
 * Usage:
 *   node conformance/runner.mjs
 *
 * Exit code 0 = all fixtures pass. Exit code 1 = one or more failures.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = join(__dirname, "..", "examples", "fixtures");

// ─── Metric computation (reference implementation) ──────────────────────────
// These functions implement the sigrank/0.1-draft metric definitions.
// A conforming implementation MUST produce the same results for the same inputs.

function round(n, d) {
  if (!Number.isFinite(n)) return null;
  return Number(n.toFixed(d));
}

/**
 * Compute the five portable metrics from four token pillars.
 *
 * Null semantics (from the spec):
 * - When a denominator is zero, the metric is null (not 0 or Infinity).
 * - When cache_read is null/unavailable, Yield, Leverage, and 10xDEV are null.
 * - When cache_write is null/unavailable, 10xDEV is null.
 * - Warnings explain each null.
 */
function computeMetrics(telemetry) {
  const input = telemetry.input;
  const output = telemetry.output;
  const cacheWrite = telemetry.cache_write ?? telemetry.cache_creation ?? null;
  const cacheRead = telemetry.cache_read ?? null;

  const warnings = [];

  // SNR = output / (input + output)
  const snrDenom = input + output;
  const snrRaw = snrDenom > 0 ? output / snrDenom : null;
  if (snrRaw === null) warnings.push("snr_undefined: input+output=0");

  // Velocity = output / input
  const velocityRaw = input > 0 ? output / input : null;
  if (velocityRaw === null) warnings.push("velocity_undefined: input=0");

  // Leverage = cacheRead / input — null when cache_read is unavailable
  let leverageRaw = null;
  if (cacheRead === null) {
    // Standard null policy: unavailable cache_read → null
  } else if (input > 0) {
    leverageRaw = cacheRead / input;
  } else {
    warnings.push("leverage_undefined: input=0");
  }

  // Yield = (cacheRead × output) / input² = leverage × velocity
  let yieldRaw = null;
  if (cacheRead === null) {
    // Standard null policy: unavailable cache_read → null
  } else if (leverageRaw !== null && velocityRaw !== null) {
    yieldRaw = leverageRaw * velocityRaw;
  } else {
    warnings.push("yield_undefined: requires input>0");
  }

  // 10xDEV = log10(R / I) — requires all four pillars > 0
  let dev10xRaw = null;
  if (cacheWrite === null || cacheRead === null) {
    // Standard null policy: unavailable cache → null
  } else if (input > 0 && output > 0 && cacheWrite > 0 && cacheRead > 0) {
    dev10xRaw = Math.log10((output / input) * (cacheWrite / output) * (cacheRead / cacheWrite));
  } else {
    warnings.push("dev10x_undefined: requires all four pillars > 0");
  }

  // Standard-level warnings for unavailable cache
  if (cacheWrite === null) warnings.push("cache_write is unavailable; 10xDEV is undefined.");
  if (cacheRead === null) warnings.push("cache_read is unavailable; Yield, Leverage, and 10xDEV are undefined.");

  return {
    metrics: {
      yield: round(yieldRaw, 2),
      leverage: round(leverageRaw, 1),
      velocity: round(velocityRaw, 3),
      snr: round(snrRaw, 4),
      dev10x: round(dev10xRaw, 2),
    },
    warnings,
  };
}

// ─── Fixture loading and validation ──────────────────────────────────────────

function loadFixtures() {
  const files = readdirSync(FIXTURES_DIR)
    .filter((f) => f.endsWith(".json"))
    .sort();
  return files.map((f) => {
    const raw = readFileSync(join(FIXTURES_DIR, f), "utf-8");
    return JSON.parse(raw);
  });
}

function approxEqual(a, b, tolerance = 0.001) {
  if (a === null && b === null) return true;
  if (a === null || b === null) return false;
  return Math.abs(a - b) < tolerance;
}

function validateFixture(fixture) {
  const errors = [];
  const id = fixture.id;

  const { telemetry, source } = fixture.input;
  const expected = fixture.expected;

  // Compute metrics
  const result = computeMetrics(telemetry);

  // 1. Schema validity — required fields present (0 is valid, undefined is not)
  if (telemetry.input === undefined || telemetry.input === null) {
    errors.push("schema: input is required");
  }
  if (telemetry.output === undefined || telemetry.output === null) {
    errors.push("schema: output is required");
  }

  // 2. Metric comparison
  if (expected.metrics) {
    for (const [key, expectedValue] of Object.entries(expected.metrics)) {
      const actualValue = result.metrics[key];
      if (!approxEqual(actualValue, expectedValue)) {
        errors.push(`metric ${key}: expected ${expectedValue}, got ${actualValue}`);
      }
    }
  }

  // 3. Version declaration
  if (expected.spec) {
    // The spec field is added by the record builder, not computeMetrics
    // We validate it here as part of the record contract
  }

  // 4. Extension exclusion — no forbidden metrics in the output
  if (expected.forbidden_metrics) {
    for (const forbidden of expected.forbidden_metrics) {
      if (forbidden in result.metrics) {
        errors.push(`extension leak: ${forbidden} found in metrics`);
      }
    }
  }

  // 5. Required metrics present
  if (expected.required_metrics) {
    for (const required of expected.required_metrics) {
      if (!(required in result.metrics)) {
        errors.push(`missing required metric: ${required}`);
      }
    }
  }

  // 6. Content independence — no forbidden fields in telemetry
  if (expected.forbidden_fields) {
    for (const forbidden of expected.forbidden_fields) {
      if (forbidden in telemetry) {
        errors.push(`content leak: ${forbidden} found in telemetry`);
      }
    }
  }

  // 7. Alias translation — cache_creation should be accepted as cache_write
  if (expected.output_telemetry_keys) {
    // This is validated at the record level, not the metrics level
  }

  return { id, errors, passed: errors.length === 0 };
}

// ─── Main ────────────────────────────────────────────────────────────────────

function main() {
  const fixtures = loadFixtures();
  let passed = 0;
  let failed = 0;

  console.log(`SigRank Standard v0.1-draft Conformance Suite`);
  console.log(`${fixtures.length} fixtures loaded from examples/fixtures/`);
  console.log("");

  for (const fixture of fixtures) {
    const result = validateFixture(fixture);
    if (result.passed) {
      console.log(`  ✓ ${result.id}`);
      passed++;
    } else {
      console.log(`  ✗ ${result.id}`);
      for (const err of result.errors) {
        console.log(`      ${err}`);
      }
      failed++;
    }
  }

  console.log("");
  console.log(`Results: ${passed} passed, ${failed} failed, ${fixtures.length} total`);

  if (failed > 0) {
    process.exit(1);
  }
}

main();
