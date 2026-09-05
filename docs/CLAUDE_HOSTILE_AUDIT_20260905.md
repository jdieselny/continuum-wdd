# Hostile Audit Report — Genesis Block Cryptographic Remediation

- **Auditor:** Claude (adversarial role), WO_20260905_002_CLAUDE_GENESIS_AUDIT
- **Audit date:** 2026-09-05
- **Target repo:** `~/Documents/continuum-wdd`
- **Audited HEAD:** `82632b49ae5e80aaa4b2420a4c077be410c21b14` (confirmed)
- **HEAD tree:** `be5e3926b2862865a4f22c7b6c14684ea9f46b91`
- **Method:** fresh `git clone` + isolated venv (no inherited packages), independent tamper harness. Grok's own tests were re-run but **not relied upon** for any conclusion.

## Verdict

**The cryptographic core HOLDS. The attestation layer does NOT.**

Every invariant Iman flagged is genuinely closed: full canonical binding, PEM-based revocation, digest-bound ledger, and a verifier that actually executes and fails closed. I could not forge, tamper, replay, or downgrade my way past it.

However, the **Genesis Seal does not attest to the audited HEAD**, and CI is red at HEAD. **Do not send a tree SHA to Dr. Schrock until F-1 through F-4 are closed.**

## Results by requirement

| § | Requirement | Result |
|---|---|---|
| 2.1 | Clean-clone dependencies | **PASS** |
| 2.2 | Key revocation + `.gitignore` | **PASS** |
| 2.3 | Workorder tamper / canonical binding | **PASS** |
| 2.3 | Ledger digest binding | **PASS** |
| 2.3 | WO-032 tree SHA + manifest signed | **FAIL** (F-2, F-3) |
| 2.4 | Replay past block 1, 29 non-genesis links | **PASS** |
| 2.4 | Adversarial negative tests | **PASS** (verifier proven live) |
| — | CI green at HEAD | **FAIL** (F-1) |

### 2.1 Clean-clone dependencies — PASS

Fresh venv confirmed to lack both deps, then `pip install -e ".[dev]"` resolved `cryptography 50.0.1` and `jsonschema 4.26.0` from `pyproject.toml` declarations (`cryptography>=42.0.0`, `jsonschema>=4.20.0`). `wdd validate` and `wdd replay --benchmark` both exit `0` out of the box with **no manual pip intervention**. `wdd init` correctly refuses to overwrite immutable intent (exit `1`).

### 2.2 Key revocation and gitignore — PASS

- Private keys ignored at two levels (root `.gitignore` + `keys/.gitignore`); `git check-ignore` confirms `keys/agent_private.pem` is ignored. No private key is tracked at HEAD, and a clean clone contains none.
- `wdd keygen` writes a private key that lands **already ignored** — the regeneration leak path is closed.
- Old compromised key (`agent_key_v0_compromised`, committed in `6bf5b10`) is present in `revoked[]` with reason and historical commit.
- Local private key derives to the **new** active public key, not the revoked one — rotation is real, not cosmetic.

**Revocation is enforced by public-key PEM, not by `key_id` or `status`.** I attacked it two ways and both failed:

- Re-enrolling the revoked PEM under a fresh `key_id` (`sneaky_key`, status ACTIVE) → still refused.
- Flipping the revoked entry's `status` to ACTIVE in place → still refused.

This is the correct design and it resists the obvious bypasses.

### 2.3 Cryptographic binding — PASS (binding) / FAIL (attestation)

`canonical.workorder_signing_payload` signs the **entire** workorder body minus the detached `issuer_signature`. I verified this exhaustively rather than trusting it — tampering each of the **21 fields independently**, plus field insertion and field deletion:

```
$schema, workorder_id, version, created_at, issuer, assigned_to, action,
priority, grid_squares, domain_tag, title, status, description, dependencies,
deliverables, requirements, acceptance_criteria, failure_modes, nonce,
expires_at, token_projection          -> ALL 21 bound (rejected)
add new field / delete 'action'       -> bound (rejected)

UNBOUND FIELDS: NONE
```

The specific test mandated by the workorder — mutating `action` from `cli.engine.init` to `trust.crypto.keygen` — is rejected with `workorder signature verification failed`. **Full canonical binding is proven, not ID-only binding.**

Ledger entries store exact `workorder_digest` and `receipt_digest`, recomputed and compared on every replay. Forging a digest and recomputing `current_hash` to repair the chain is still caught by the digest comparison.

### 2.4 Replay — PASS

Clean-clone `wdd replay --benchmark`: **30 blocks verified** (genesis + 29 non-genesis links), full chain resolves, every workorder and receipt signature verified, exit `0`. Survives well past block 1.

### 2.4 Adversarial negative testing — PASS

Independent harness, 13 attacks in isolated sandboxes. **The verifier is live — it does not fall back to schema-only PASS.**

| Attack | Outcome |
|---|---|
| control: untampered ledger | passes (correct) |
| receipt artifact deleted | BLOCKED — `receipt artifact missing` |
| workorder artifact deleted | BLOCKED — `workorder artifact missing` |
| `max_token_burn` exceeded | BLOCKED — `Token burn 9999999 exceeds rubric max 100` |
| receipt signature stripped | BLOCKED — `missing receipt signature` |
| receipt body tampered | BLOCKED — `receipt signature verification failed` |
| workorder `action` tampered | BLOCKED — `workorder signature verification failed` |
| workorder signature removed | BLOCKED — `missing issuer_signature` |
| ledger `previous_hash` broken | BLOCKED — `Hash chain broken at block 0` |
| `workorder_digest` forged + hash repaired | BLOCKED — `workorder_digest mismatch` |
| `receipt_digest` field removed | BLOCKED — `missing required field` |
| trust registry deleted | BLOCKED — fails **closed**, not open |
| `rubric.json` deleted under `--benchmark` | BLOCKED — `rubric.json not found` |

Deleting the trust registry causes refusal rather than a silent pass — the fail-closed property Iman asked for.

## Findings

### F-1 — HIGH — CI is red at HEAD; the binding proof never executes

`pytest tests/` passes **14/14 locally** but **12/14 in a clean clone**. Two tests call `load_private_key(ROOT/"keys"/"agent_private.pem")`, which is correctly gitignored and therefore absent from any clone:

- `test_id_only_signature_rejected` — the canonical-binding proof
- `test_max_token_burn_violation_fails` — the rubric adversarial test

`.github/workflows/ci.yml` runs `pytest tests/ -v` on a bare checkout with **no keygen step**, so CI fails on every push. The two invariants Grok most needs to demonstrate are exactly the two that cannot run in CI.

**Fix:** have these tests generate an ephemeral keypair in `setUp` and enroll it in a temp registry, rather than depending on developer-local private material.

### F-2 — HIGH — The Genesis Seal does not attest to HEAD

WO-032's sealed `tree_sha` is `50b97cb61940519cb9b90d6468896e1ec55628e2`, which is the tree of commit `06631b4` — **two commits behind HEAD**.

```
HEAD 82632b4 tree : be5e3926b2862865a4f22c7b6c14684ea9f46b91
WO-032 tree_sha   : 50b97cb61940519cb9b90d6468896e1ec55628e2  (= 06631b4^{tree})
```

The seal is internally valid and its signature verifies, but it attests to a tree that is not the one under audit. Commits `30ed912` and `82632b4` — including a change to `lib/wdd/validator.py` — landed after the seal.

### F-3 — MEDIUM — The sealed manifest covers zero code

`result_manifest` lists 11 files. All 11 still hash correctly at HEAD, and `seal_evidence_digest` recomputes exactly. But the manifest contains **no `lib/` files at all** — only docs, schemas, the trust registry, `rubric.json`, `pyproject.toml`, and `README.md`.

The verifier implementation is therefore outside the attestation. `lib/wdd/validator.py` was modified in `82632b4` and the seal is blind to it. **An attacker who modifies the verifier itself does not invalidate the Genesis Seal.** Combined with F-2 this is the most substantive gap remaining.

**Fix:** include `lib/wdd/*.py` in `result_manifest` and re-seal against the final tree.

### F-4 — MEDIUM — Tracked bytecode makes the tree SHA non-reproducible

10 `.pyc` files are tracked at HEAD, including compiled `crypto`, `gate`, `validator`, and `replay`. The `__pycache__/` ignore rule is **inert** because the files were already tracked (`git ls-files -i -c` lists all 10).

Merely importing the library dirties the working tree:

```
after reset          : 0 dirty files
after importing wdd  : 5 dirty files
```

The repo cannot produce a stable tree SHA — which is precisely the artifact being certified to Iman. Shipping compiled bytecode of the verifier in a sealed tree, covered by no manifest and no signature, is also a supply-chain smell.

**Fix:** `git rm -r --cached lib/wdd/__pycache__ tests/__pycache__` and re-seal.

### F-5 — MEDIUM — `wdd validate` passes any JSON lacking `$schema`

`validator._schema_validate_file` returns `[]` immediately when `$schema` is absent. An unsigned forged workorder saved as `mailbox/archive/payload-996.json` with `$schema` removed is reported `PASS`. The filename-based dispatch at `validator.py:185-195` only routes files matching `wo-*.json` into `_verify_workorder_file`.

Not exploitable against the Genesis chain: such a file cannot enter the ledger without a validly-signed receipt, and `replay` independently verifies every workorder signature. Rated Medium as a defense-in-depth weakness — `validate` should not be mistaken for a complete admission gate.

**Fix:** treat missing `$schema` inside `mailbox/` and `workorders/` as an error, and dispatch on content (`workorder_id` present) rather than filename.

### F-6 — LOW — Ledger signature failures escape as a traceback

`_verify_ledger_dir` catches only `ReplayError`, but signature failures raise `ValueError`. With a tampered ledger artifact, `wdd validate` emits an uncaught traceback instead of a clean `FAIL:` line. It still exits `1` (fails closed), and the workorder-level check does report cleanly — this is ergonomics, not a bypass.

### F-7 — LOW / advisory — The trust registry is unsigned

`trust_registry.v1.json` has no signature. Anyone with write access can delete the `revoked[]` entry and re-add the compromised key. The root of trust is the git tree itself, which is defensible, but worth stating explicitly to Iman rather than leaving implicit.

### F-8 — LOW / advisory — `keygen` rotation does not auto-revoke

`generate_keys` replaces the active `agent_key` without adding the superseded key to `revoked[]`. It fails closed (the old PEM is simply no longer ACTIVE), but no revocation audit trail is produced. Revocation currently requires a manual `revoke_key` call.

### F-9 — Informational — Dead fallback branch

`gate.verify_receipt_signature:96-104` re-implements the lookup after `get_active_public_pem` returns `None`. I traced both reachable cases; it re-checks `status == ACTIVE` and `is_revoked_pem`, so it is **redundant but safe**. Not a bypass. Recommend deleting it so it cannot rot into one.

### F-10 — Informational — `max_token_burn` is vacuous on live data

All 30 real receipts carry `token_burn: 0` against a limit of 5,000,000. The check is genuinely enforced (proven synthetically above), but it exercises nothing on the real chain.

## Tree SHA recommendation

**Withholding sign-off.** The two candidate SHAs disagree and neither is currently safe to transmit:

- `be5e3926b2862865a4f22c7b6c14684ea9f46b91` — HEAD's tree, but **not covered by the WO-032 seal** (F-2) and not reproducible (F-4).
- `50b97cb61940519cb9b90d6468896e1ec55628e2` — the sealed tree, but two commits stale and missing the `82632b4` validator fix.

Required before a SHA goes to Dr. Schrock:

1. Untrack all `.pyc` (F-4) so the tree is reproducible.
2. Add `lib/wdd/*.py` to `result_manifest` (F-3).
3. Re-seal WO-032 against the resulting final tree and append the ledger entry (F-2).
4. Make the adversarial tests self-provisioning so CI is green (F-1).

After those, re-run this audit and the newly sealed `tree_sha` will equal HEAD's tree and can be sent with confidence.

## Bottom line for Iman

The cryptographic remediation is sound. Signatures bind the full canonical workorder body, revocation is enforced by key material rather than by label, the ledger is digest-bound, and the verifier demonstrably executes and fails closed under thirteen distinct attacks. Grok's crypto work survived hostile review.

What has not been closed is the **attestation wrapper**: the seal points at a stale tree, covers no executable code, sits in a repo that cannot reproduce a stable tree hash, and is guarded by a CI job that is currently failing. These are bookkeeping defects rather than cryptographic ones, but they are exactly the defects that make a tree SHA meaningless as evidence.
