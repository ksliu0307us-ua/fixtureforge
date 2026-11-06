# FixtureForge roadmap

All items are proposed and unimplemented. Total estimate: **30 engineering hours**.

## Dataset relationships — 6 hours

Generate multiple named datasets with deterministic foreign-key relationships.

Acceptance criteria: references always resolve; dependency order is validated;
cycles and impossible row counts produce clear errors; seeds remain reproducible.

## Uniqueness and nullable fields — 5 hours

Add explicit uniqueness constraints and seeded null probabilities.

Acceptance criteria: impossible uniqueness is rejected before output; nulls have
documented JSON/CSV forms; constraints and reproducibility have boundary tests.

## Dependent-field templates — 6 hours

Allow fields to derive strings from earlier fields with explicit dependency graphs.

Acceptance criteria: unknown references and cycles are rejected; escaping is
documented; templates cannot access the environment or execute code.

## JSONL and SQL exports — 5 hours

Add streaming JSON Lines and portable SQL INSERT output.

Acceptance criteria: quoting is injection-safe; dialect limits are documented;
zero-row and Unicode fixtures round-trip in integration tests.

## Schema-version migration — 4 hours

Add an explicit dry-run migration command for future schema versions.

Acceptance criteria: original files remain unchanged by default; migrations are
idempotent and version-stepped; unsupported paths fail without partial output.

## Packaging and compatibility matrix — 4 hours

Verify supported Python versions and major operating systems in CI.

Acceptance criteria: Python 3.11+ runs on Windows, macOS, and Linux; wheel and source
installations are exercised outside the source tree; reproducibility fixtures detect
unexpected output changes.
