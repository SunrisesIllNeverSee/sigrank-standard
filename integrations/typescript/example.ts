/**
 * integrations/typescript/example.ts
 *
 * Minimal TypeScript implementation of the SigRank Standard v0.1-draft
 * five-metric portable core. No dependencies.
 *
 * A conforming implementation MUST produce the same results as the
 * conformance suite fixtures for the same inputs.
 */

export interface Telemetry {
  input: number;
  output: number;
  cache_write?: number | null;
  cache_read?: number | null;
}

export interface Metrics {
  yield: number | null;
  leverage: number | null;
  velocity: number | null;
  snr: number | null;
  dev10x: number | null;
}

export interface StandardRecord {
  spec: "sigrank/0.1-draft";
  timestamp: string;
  source: {
    provider: string;
    model: string;
    tool: string;
  };
  telemetry: {
    input: number;
    output: number;
    cache_write: number | null;
    cache_read: number | null;
  };
  metrics: Metrics;
  warnings: string[];
}

function round(n: number | null, d: number): number | null {
  if (n === null || !Number.isFinite(n)) return null;
  return Number(n.toFixed(d));
}

export function computeMetrics(t: Telemetry): { metrics: Metrics; warnings: string[] } {
  const input = t.input;
  const output = t.output;
  const cacheWrite = t.cache_write ?? null;
  const cacheRead = t.cache_read ?? null;
  const warnings: string[] = [];

  const snr = input + output > 0 ? output / (input + output) : null;
  if (snr === null) warnings.push("snr_undefined: input+output=0");

  const velocity = input > 0 ? output / input : null;
  if (velocity === null) warnings.push("velocity_undefined: input=0");

  let leverage: number | null = null;
  if (cacheRead === null) {
    // unavailable → null
  } else if (input > 0) {
    leverage = cacheRead / input;
  } else {
    warnings.push("leverage_undefined: input=0");
  }

  let y: number | null = null;
  if (cacheRead === null) {
    // unavailable → null
  } else if (leverage !== null && velocity !== null) {
    y = leverage * velocity;
  } else {
    warnings.push("yield_undefined: requires input>0");
  }

  // Standard-level warnings for unavailable cache (emitted before dev10x
  // warning so the "why" precedes the "what" in the warning list)
  if (cacheWrite === null) warnings.push("cache_write is unavailable; 10xDEV is undefined.");
  if (cacheRead === null) warnings.push("cache_read is unavailable; Yield, Leverage, and 10xDEV are undefined.");

  let dev10x: number | null = null;
  if (cacheWrite === null || cacheRead === null) {
    // unavailable → null
    warnings.push("dev10x_undefined: requires all four pillars > 0");
  } else if (input > 0 && output > 0 && cacheWrite > 0 && cacheRead > 0) {
    dev10x = Math.log10(cacheRead / input);
  } else {
    warnings.push("dev10x_undefined: requires all four pillars > 0");
  }

  return {
    metrics: {
      yield: round(y, 2),
      leverage: round(leverage, 1),
      velocity: round(velocity, 3),
      snr: round(snr, 4),
      dev10x: round(dev10x, 2),
    },
    warnings,
  };
}

export function buildRecord(t: Telemetry, source: { provider: string; model: string; tool: string }): StandardRecord {
  const { metrics, warnings } = computeMetrics(t);
  return {
    spec: "sigrank/0.1-draft",
    timestamp: new Date().toISOString(),
    source,
    telemetry: {
      input: t.input,
      output: t.output,
      cache_write: t.cache_write ?? null,
      cache_read: t.cache_read ?? null,
    },
    metrics,
    warnings,
  };
}
