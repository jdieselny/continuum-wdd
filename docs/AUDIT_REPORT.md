# AUDIT REPORT — WDD Genesis Block

| | |
|---|---|
| **Workorder** | `wo-000-genesis-audit` |
| **Auditor** | `agent:opus.jdieselny.com` |
| **Issuer** | `principal_justin_kintzele` |
| **Date** | 2026-09-04 |
| **Scope** | `docs/HOLEMAP.md`, `schemas/*.json`, `README.md`, `mailbox/` tree |
| **Verdict** | **CONDITIONAL PASS** — the architecture is coherent; the plan as written could not execute. 26 workorders added. |

---

## 1. Verdict

The Genesis Block is architecturally sound in intent and unbuildable as sequenced.

The original queue (WO-000..WO-006) is a list of **components**, not a **build**. It names the
schemas, the CLI, the compiler and the GUIs, but omits every piece of plumbing that connects them:
how the first workorder gets executed before the executor exists, where execution is recorded, what
`replay` replays, who is allowed to put work in the mailbox, and how anyone knows the build
succeeded. Approving it as-is would have been the exact failure mode this workorder warns against.

I have **not** rejected the plan. I have expanded it from 7 workorders to 33 (WO-000..WO-032,
matching the range `README.md` already advertises), added three grid squares, and imposed a phased
execution sequence.

---

## 2. Blocking Findings

### F-1 — Bootstrap paradox: `wdd replay` cannot build `wdd` *(CRITICAL)*

`README.md` opens with `python wdd replay`, which "replays the Genesis Block (WO-000 through
WO-032)" to construct the engine. But the `wdd` CLI **is** WO-001, and the replay engine does not
appear in the queue at all. The artifact required to run the build is an output of the build.

There is also no `wdd` file, no `pyproject.toml`, and no Python source anywhere in the repository —
`lib/` is empty. Both README quickstart commands fail with `can't open file 'wdd'`.

**Resolution:** WO-007 (stage-0 `bootstrap.py`, pure stdlib, no WDD dependencies — the seed that
executes the first envelopes by hand-off) and WO-008 (packaging and the real `wdd` entrypoint).
Phase 0 exists solely to break this circularity. Nothing else can precede it.

### F-2 — Replay has no substrate to replay from *(CRITICAL)*

Replay is the product's headline claim and its "Training / Benchmark Mode". Replay requires a
durable, ordered record of what happened. Nothing in the original queue records anything:
`mailbox/archive/` and `mailbox/receipts/` exist as empty directories referenced by no workorder,
and there is no journal schema.

**Resolution:** new square **E-01**. WO-010 (`ledger.schema.json`, hash-chained entries),
WO-021 (recorder — every state transition appends), WO-022 (`wdd replay`), WO-023 (golden outputs
and a pass/fail rubric, because a benchmark with no scoring function is a demo).

### F-3 — The mailbox is an unauthenticated remote-execution surface *(CRITICAL)*

This is the most serious security gap. As designed:

- `receipt.schema.json` requires a signature. `workorder.schema.json` **does not.** Outputs are
  signed; inputs are not. That is backwards for an ingress point.
- Any process that can write a file into `mailbox/inbox/` gets an autonomous agent to execute an
  arbitrary `action` verb with arbitrary `payload` and `requirements`. There is no allowlist of
  actions, no sandbox, no capability model.
- `assigned_to: "agent:opus.jdieselny.com"` implies an agent identity namespace with no enrollment
  record, no public key, and no way to verify an executor is who the envelope says it is.
- `description` and `requirements` are free-text fields fed to an LLM executor. Unsigned, they are a
  direct prompt-injection channel into a system with filesystem write access.
- No `nonce` and no `expires_at`: re-dropping a previously executed envelope re-executes it.
- `signature.alg` offers `Ed25519 | ML-DSA-65 | Hybrid-PQC` with no keygen, no trust store, and no
  verification path — the crypto is declared, not implemented.

**Resolution:** new square **F-01**. WO-012 (agent enrollment + keys), WO-015 (signed inbound
envelopes, reject-unsigned in enforcing mode), WO-016 (`wdd keygen` + `keys/trusted.json`),
WO-017 (deny-by-default action registry + sandbox policy), WO-018 (receipt issuance),
WO-019 (nonce/expiry/idempotency), WO-028 (written threat model).

---

## 3. Structural Findings

### F-4 — No lifecycle state machine

`docs/HOLEMAP.md` uses `OPEN` and `HOLE`; `wo-000-genesis-audit.json` carries a top-level `status`
field. **`status` is not a property in `workorder.schema.json` at all** — it validates only because
`additionalProperties: true`. The set of legal states and legal transitions is undefined, so no two
implementers will agree on it. Same for `dependencies`, which WO-000 uses and the schema never
declares.

**Resolution:** WO-009 ratifies both properties and the transition table. A provisional vocabulary
is recorded at the foot of `HOLEMAP.md` so work can proceed before ratification.

### F-5 — `mailbox/processing/` is referenced but does not exist

`lease_timeout_sec` is documented as "lease duration before lock expires in `/mailbox/processing/`".
That directory is not in the tree. There is likewise no `mailbox/failed/` despite every workorder
carrying a `failure_modes` array — a failing workorder currently has nowhere to go and no retry or
escalation policy. Note also that the four existing mailbox directories are empty and contain no
`.gitkeep`, so **git will not preserve them on clone**; a fresh clone of this repo loses
`outbox/`, `archive/` and `receipts/` entirely.

**Resolution:** WO-014 (directory contract, lease file format, expiry reclaim, `.gitkeep` policy),
WO-020 (dead-letter path, attempt counter, backoff, escalation).

### F-6 — Nothing validates envelopes against the schemas

Two strict JSON Schemas exist. No workorder loads them. WO-006 *refines* the schema without anything
ever *enforcing* it, which means the schemas are documentation, not contracts.

**Resolution:** WO-013 (`wdd validate`, non-zero exit) and WO-027 (CI gate).

### F-7 — The Hole Map is a hand-maintained duplicate of the mailbox

The queue table and `mailbox/inbox/` describe the same facts. Nothing keeps them in sync, so they
will diverge — this audit is itself a hand-edit of a file that should be generated. The Hole Map
should be a *rendering* of mailbox state.

**Resolution:** WO-024 (synchronizer; the table becomes generated output).

### F-8 — No dependency ordering mechanism

`dependencies` is present on the envelope and consumed by nothing. Nor was the original queue
ordered correctly: WO-003 and WO-004 (GUIs) sat ahead of the data they render, and WO-001
(`wdd init`, the scaffolding generator) sat ahead of WO-002 (the compiler that produces what it
scaffolds).

**Resolution:** WO-025 (topological scheduler, cycle detection) plus the phase table now at the top
of `HOLEMAP.md`. WO-001 and WO-003/004 have been re-sequenced into phases 4 and 5.

### F-9 — The telemetry dashboard has no data source

WO-004 builds a telemetry dashboard. No workorder produces telemetry, and no telemetry event schema
exists. It would ship as static mock UI.

**Resolution:** WO-011 (`telemetry.schema.json`) and WO-026 (emitter + feed), both sequenced ahead
of WO-004.

---

## 4. Contract and Hygiene Findings

| # | Finding | Resolution |
|---|---|---|
| F-10 | **"crypto BOL" is undefined.** WO-005 requires verifying a "crypto BOL". The term appears in no schema. If it means the EP-RECEIPT, say `receipt`; if it is a distinct bill-of-lading artifact, it needs its own schema and workorder. | WO-005 amended to force the decision |
| F-11 | **Namespace mismatch.** Both schemas declare `$id: https://aib.emilia.ai/schemas/...` and titles under "A:iB / EMILIA", while the project is `[Continuum \| WDD]`. Provenance is ambiguous and the `$id` URIs are unresolvable. | WO-029 |
| F-12 | **CLI verbs promised but not workordered.** The B-01 square advertises `init, compile, replay, sweep`; only `init` had a workorder. | WO-030, WO-022 |
| F-13 | **The vomit prompt is discarded.** `wdd init` takes raw intent and runs a 3-pass fan-out, but nothing persists the input or the intermediate passes — so an `init` run is not auditable and not replayable. | WO-031 |
| F-14 | **No LICENSE, CONTRIBUTING, SECURITY.md, or CI.** For a repo whose thesis is verifiable autonomous execution, absence of a security disclosure path is a notable omission. | WO-028, WO-027 |
| F-15 | **No terminal seal.** Nothing declares the Genesis Block complete. Without a defined finish line, "self-hosting" is unfalsifiable. | WO-032 |

---

## 5. Additions to the Hole Map

Three squares added: **E-01** (Ledger & Replay), **F-01** (Trust & Mailbox Security),
**G-01** (Quality & Governance).

Twenty-six workorders added, WO-007..WO-032. Existing IDs WO-001..WO-006 are unchanged and
unrenumbered; they were re-sequenced by phase, not rewritten. A `Phase` column and a `Depends On`
column were added to the queue table, and a provisional status vocabulary was appended.

| Square | Added | Count |
|---|---|---|
| A-01 | WO-009, WO-010, WO-011, WO-012, WO-029 | 5 |
| B-01 | WO-007, WO-008, WO-013, WO-020, WO-030 | 5 |
| C-01 | WO-024, WO-025, WO-031 | 3 |
| D-01 | WO-026 | 1 |
| E-01 | WO-021, WO-022, WO-023, WO-032 | 4 |
| F-01 | WO-014, WO-015, WO-016, WO-017, WO-018, WO-019 | 6 |
| G-01 | WO-027, WO-028 | 2 |

The critical path is now:
**WO-007 → WO-008 → WO-009 → WO-013 → WO-014 → WO-018 → WO-021 → WO-022 → WO-023 → WO-032.**

---

## 6. Note on This Workorder's Own Disposition

WO-000 could not be closed through the mailbox lifecycle, because the mailbox lifecycle is WO-005
and WO-014, and no receipt could be issued, because the signing authority is WO-016 and WO-018. The
result envelope at `mailbox/outbox/wo-000-genesis-audit.result.json` is therefore **self-attested and
unsigned**, and `mailbox/inbox/wo-000-genesis-audit.json` was left in place rather than moved, since
no runner owns that transition yet.

That is not a workaround; it is the audit's thesis reproduced in miniature. The first workorder of a
self-hosting system cannot be sealed by the system it builds. Once WO-018 lands, this envelope
should be re-swept and retroactively sealed as the ledger's first entry — which is precisely what
WO-032 must verify.

---

## 7. Recommendation

Proceed to **Phase 0**. Do not begin WO-001 through WO-004 until Phases 0–2 are sealed; building the
GUIs against an unauthenticated mailbox with no ledger would produce a convincing demo of a system
that cannot prove anything it displays.
