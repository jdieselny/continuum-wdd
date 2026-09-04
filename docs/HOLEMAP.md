# HOLE MAP: WDD Genesis Block

**Domain:** `[Continuum | WDD]`
**Objective:** The self-hosting Workorder Driven Development engine.

This is the Genesis Block. These workorders construct the WDD engine itself. Once complete, this repository becomes the canonical CLI/GUI for instantiating new WDD projects.

> **Audit status:** Expanded by WO-000 (Architect audit, 2026-09-04). See `docs/AUDIT_REPORT.md`
> for findings. The original queue (WO-000..WO-006) described *what* to build but not *how the
> build bootstraps, proves itself, or defends itself*. Squares E-01, F-01 and G-01 and workorders
> WO-007..WO-032 were added to close those holes.

## Grid Squares (The Scaffold)
- **A-01 [Core Schemas]:** The strict JSON definitions and the contracts derived from them.
- **B-01 [CLI Engine]:** The `wdd` python CLI (bootstrap, init, validate, compile, sweep, replay).
- **C-01 [OB Writer Backend]:** The 3-pass intent processor and the Hole Map synchronizer.
- **D-01 [Glass / GUI]:** The React/HTML MMC snap-ins (Dashboard, OB Writer) and their data feeds.
- **E-01 [Ledger & Replay]:** *(added by WO-000)* The append-only execution journal and the replay
  engine. Replay is the headline feature in `README.md` and had no workorder backing it.
- **F-01 [Trust & Mailbox Security]:** *(added by WO-000)* Identity, signatures, key management,
  action allowlisting, receipts and lease mechanics. The mailbox is an untrusted ingress point and
  the original queue treated it as trusted.
- **G-01 [Quality & Governance]:** *(added by WO-000)* Tests, CI, licensing, threat model.

## Execution Sequence

Workorder IDs are stable and are **not** execution order. Execute by phase; within a phase,
respect `dependencies`.

| Phase | Name | Workorders |
|---|---|---|
| 0 | Bootstrap (stage-0 seed) | WO-007, WO-008 |
| 1 | Contracts | WO-006, WO-009, WO-010, WO-011, WO-012, WO-013, WO-029 |
| 2 | Mailbox & Trust | WO-014, WO-015, WO-016, WO-017, WO-018, WO-019, WO-020, WO-005 |
| 3 | Ledger & Replay | WO-021, WO-022, WO-023 |
| 4 | Compiler / OB Writer | WO-002, WO-024, WO-025, WO-031, WO-001 |
| 5 | Glass | WO-026, WO-004, WO-003 |
| 6 | Seal | WO-027, WO-028, WO-030, WO-032 |

## The Queue

| ID | Square | Phase | Description | Depends On | Status |
|---|---|---|---|---|---|
| **WO-000** | A-01 | — | Peer Review: Architect audit of the Genesis Block | — | DONE |
| **WO-007** | B-01 | 0 | Stage-0 bootstrap runner (`bootstrap.py`): read one envelope, dispatch, record result. Pure stdlib, no WDD deps. | — | HOLE |
| **WO-008** | B-01 | 0 | Packaging: `pyproject.toml`, `wdd/` package, `python -m wdd` + `wdd` console entrypoint. Makes the README quickstart executable. | WO-007 | HOLE |
| **WO-006** | A-01 | 1 | Schemas: refine `workorder.schema.json` with token projections | WO-008 | HOLE |
| **WO-009** | A-01 | 1 | Lifecycle state machine: enumerate `status` (OPEN/LEASED/BLOCKED/DONE/SEALED/FAILED/CANCELLED), promote `dependencies` to a validated property, define legal transitions | WO-008 | HOLE |
| **WO-010** | A-01 | 1 | `schemas/ledger.schema.json`: hash-chained append-only journal entry. The substrate replay reads. | WO-009 | HOLE |
| **WO-011** | A-01 | 1 | `schemas/telemetry.schema.json`: event envelope the dashboard consumes | WO-009 | HOLE |
| **WO-012** | A-01 | 1 | `schemas/agent.schema.json`: agent enrollment record, public keys, capability grants | WO-009 | HOLE |
| **WO-013** | B-01 | 1 | `wdd validate`: validate every envelope in `mailbox/`, `workorders/`, `ledger/` against schemas; non-zero exit on failure | WO-009 | HOLE |
| **WO-029** | A-01 | 1 | Namespace decision: reconcile `$id` host `aib.emilia.ai` with `[Continuum \| WDD]`; canonicalize schema URIs and `$schema` refs | WO-006 | HOLE |
| **WO-014** | F-01 | 2 | Mailbox directory contract: create `processing/` and `failed/`, `.gitkeep` policy, lease file format, expired-lease reclaim | WO-009 | HOLE |
| **WO-015** | F-01 | 2 | Signed inbound workorders: detached issuer signature block; reject unsigned envelopes in enforcing mode | WO-012, WO-016 | HOLE |
| **WO-016** | F-01 | 2 | Key management: `wdd keygen`, trust store `keys/trusted.json`, Ed25519 now with ML-DSA-65 migration path | WO-012 | HOLE |
| **WO-017** | F-01 | 2 | Action registry: deny-by-default allowlist of `action` verbs + execution sandbox policy | WO-015 | HOLE |
| **WO-018** | F-01 | 2 | Receipt issuance: gate that emits `mailbox/receipts/*.json` conforming to `receipt.schema.json` on every terminal transition | WO-016 | HOLE |
| **WO-019** | F-01 | 2 | Replay-attack defence: `nonce` + `expires_at` on envelopes, processed-ID set, idempotent re-delivery | WO-015 | HOLE |
| **WO-020** | B-01 | 2 | Dead-letter path: `mailbox/failed/`, attempt counter, backoff, operator escalation on `failure_modes` hit | WO-014 | HOLE |
| **WO-005** | B-01 | 2 | Mailbox Runner: sweep outbox, verify receipt signature, mark SEALED. **Define "crypto BOL"** or retire the term in favour of `receipt`. | WO-014, WO-018 | HOLE |
| **WO-021** | E-01 | 3 | Ledger recorder: every state transition appends a hash-chained entry to `ledger/genesis.jsonl` | WO-010 | HOLE |
| **WO-022** | E-01 | 3 | `wdd replay`: deterministic playback/re-execution from the ledger. The README's headline feature. | WO-021 | HOLE |
| **WO-023** | E-01 | 3 | Benchmark rubric: golden outputs + pass/fail scoring so "Benchmark Mode" is falsifiable | WO-022 | HOLE |
| **WO-002** | C-01 | 4 | Engine: 3-pass OB Intent Processor (`compiler.py`) | WO-008, WO-009 | HOLE |
| **WO-024** | C-01 | 4 | Hole Map synchronizer: `docs/HOLEMAP.md` table is *generated* from the mailbox, not hand-edited. One source of truth. | WO-013 | HOLE |
| **WO-025** | C-01 | 4 | Dependency resolver: topological scheduler, cycle detection, blocked-on reporting | WO-009 | HOLE |
| **WO-031** | C-01 | 4 | Intake contract: persist the raw "vomit prompt" and all 3 pass artifacts for audit and replay | WO-002, WO-021 | HOLE |
| **WO-001** | B-01 | 4 | CLI: `wdd init` (repo scaffolding generator) | WO-002, WO-024 | HOLE |
| **WO-026** | D-01 | 5 | Telemetry feed: emitter + static/HTTP data source the dashboard reads. Dashboard currently has no data. | WO-011, WO-021 | HOLE |
| **WO-004** | D-01 | 5 | GUI: Telemetry Dashboard (`wdd_telemetry.html`) | WO-026 | HOLE |
| **WO-003** | D-01 | 5 | GUI: Original Blueprint React UI (`wdd_blueprint.html`) | WO-002 | HOLE |
| **WO-027** | G-01 | 6 | Test suite + CI: schema validation, replay determinism, signature verification | WO-013, WO-022 | HOLE |
| **WO-028** | G-01 | 6 | Governance: LICENSE, CONTRIBUTING.md, SECURITY.md, mailbox threat model | WO-017 | HOLE |
| **WO-030** | B-01 | 6 | CLI verbs `wdd compile` and `wdd sweep` promised in the B-01 square description but never workordered | WO-002, WO-005 | HOLE |
| **WO-032** | E-01 | 6 | Genesis Seal: full replay green, ledger sealed, receipts complete, tag `v1.0.0` | WO-023, WO-027 | HOLE |

## Status Vocabulary

Provisional until WO-009 ratifies it in the schema:

- **HOLE** — identified, unassigned, no envelope in `mailbox/inbox/` yet.
- **OPEN** — envelope exists in `mailbox/inbox/`, unleased.
- **LEASED** — in `mailbox/processing/`, lease timer running.
- **BLOCKED** — dependencies unmet.
- **DONE** — deliverables written, result in `mailbox/outbox/`, awaiting receipt.
- **SEALED** — receipt issued and verified, moved to `mailbox/archive/`.
- **FAILED** — in `mailbox/failed/`, attempts exhausted.
