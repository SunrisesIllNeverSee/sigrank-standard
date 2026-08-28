# SigRank Standard

**Open measurement specification for AI operator performance.**

The SigRank Standard defines a common measurement vocabulary for human operation of generative AI systems across tools, providers, models, and workflows.

## Current version

**`sigrank/0.1-draft`** — proposed open measurement specification.

## Portable core

Four non-negative integer telemetry primitives:

| Primitive | Symbol | Description |
|-----------|--------|-------------|
| Input | `I` | Fresh input-token quantity |
| Output | `O` | Output-token quantity |
| Cache Write | `W` | Token quantity written to a cache |
| Cache Read | `R` | Token quantity read from a cache |

Five derived metrics:

| Metric | Formula | Null when |
|--------|---------|-----------|
| Yield (Υ) | `(R × O) / I²` | `I = 0` or `R` unavailable |
| Leverage | `R / I` | `I = 0` or `R` unavailable |
| Velocity | `O / I` | `I = 0` |
| SNR | `O / (I + O)` | `I + O = 0` |
| 10xDEV | `log10(R / I)` | Any pillar `= 0` or unavailable |

**Construction, Build Archetypes, and RS05 are NOT part of the portable core.** They are optional SignalAF reference extensions.

## Repository structure

```text
sigrank-standard/
├── README.md                 — this file
├── docs/
│   ├── SPEC.md               — normative specification
│   ├── GLOSSARY.md           — terminology
│   ├── PRIVACY.md            — content-independence requirements
│   ├── CONFORMANCE.md        — compatibility and conformance rules
│   ├── LIMITATIONS.md        — measurement boundaries
│   ├── GOVERNANCE.md         — change control and RFC process
│   ├── CHANGELOG.md          — version history
│   ├── CANON_RECONCILIATION.md
│   ├── PRODUCT_ARCHITECTURE.md
│   ├── ARCHETYPE_STATUS.md   — extension boundary
│   └── RS05_STATUS.md        — extension boundary
├── schema/
│   └── sigrank-operator-record-v0.1.schema.json
├── examples/
│   ├── canonical-reference.json
│   └── fixtures/             — conformance test vectors
├── reference/
│   └── IMPLEMENTATION_MAP.md
├── rfc/
│   └── RFC-0001.md           — RFC template
├── conformance/
│   ├── runner.mjs            — executable conformance suite
│   └── tests/                — test implementations
├── integrations/
│   ├── typescript/           — TypeScript example
│   ├── python/               — Python example
│   ├── cli/                  — CLI example
│   └── mcp/                  — MCP tool example
└── .github/workflows/
    └── conformance.yml       — CI gate
```

## Compatibility labels

- **`SigRank Compatible — v0.1-draft`** — a system may use this label when it emits a versioned compatible record, preserves I/O/W/R semantics, and matches the published metric definitions and null policy.
- **`SigRank Conformant`** — reserved until the executable conformance suite exists and a third-party implementation passes it independently.

## Provenance

The normative documents in `docs/` were extracted from the `sigrank-app` repository (`standard/` directory, Phase 0 branch `feat/sigrank-phase-0-bridge`) with preserved content. Git history attribution is documented in `reference/EXTRACTION_LOG.md`.

## License

- **Specification documents** (`docs/`, `schema/`, `examples/`): Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Executable code** (`conformance/`, `integrations/`): Apache License 2.0

See `LICENSE` and `NOTICE` for details.

## Related

- [SignalAF](https://signalaf.com) — public leaderboard and reference implementation
- [sigrank-mcp](https://github.com/SunrisesIllNeverSee/sigrank-mcp) — CLI and MCP instrument
- [@sigrank/cascade](https://github.com/SunrisesIllNeverSee/sigrank-cascade) — canonical math package
