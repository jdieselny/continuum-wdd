# Phase 2 Hostile Audit — Genesis Block Attestation

- **Auditor:** Claude (adversarial role), WO_20260905_004_CLAUDE_PHASE2_AUDIT
- **Audit date:** 2026-09-05
- **Target repo:** `~/Documents/continuum-wdd`
- **Audited HEAD:** `09a9631ae8c2b9305c7e95dadf0a076d4821e392` (confirmed)
- **Method:** fresh `git clone` + isolated venv. Manifest digests verified against **git tree objects**, not the working tree. Grok's tests were re-run but not relied upon for any conclusion.

## Verdict: **PASS — all five failures closed. Cleared for sign-off.**

F-1 through F-5 are resolved, and F-6 was fixed unprompted. The cyclic tree-SHA construction is not just correct, it is **self-tightening**: any commit after the seal breaks the invariant and forces a re-seal. I could not forge, tamper, or drift my way past the attestation.

Two residuals remain (R-1, R-2). Neither touches the Genesis chain, and both are disclosed below and in the letter to Dr. Schrock. They are hardening items, not defects in the seal.

## Results

| Ref | Requirement | Result |
|---|---|---|
| 2.1 / F-4 | No `.pyc` tracked; tree stays clean | **PASS** |
| 2.2 / F-1 | 16/16 tests, ephemeral keys, clean clone | **PASS** |
| 2.3 / F-5 | Missing `$schema` → hard FAIL | **PASS** |
| 2.4 / F-3 | `lib/` bound by the seal manifest | **PASS** |
| 2.5 / F-2 | `wo-032.tree_sha == HEAD^^{tree}` | **PASS** |
| — / F-6 | Ledger sig failures as clean FAIL | **PASS** (fixed unprompted) |

### F-4 — Compiled artifacts — CLOSED

`0` tracked `.pyc` at HEAD; `git ls-files -i -c` returns `0` tracked-and-ignored files. The working tree stayed at **0 dirty files** through import of all seven modules, `wdd validate`, `wdd replay --benchmark`, and the full pytest run. Bytecode is still generated on disk but is correctly ignored (`**/__pycache__/` added). The tree SHA is now reproducible.

### F-1 — Clean-clone CI — CLOSED

**16/16 pass in a clean clone containing no private key.** `keys/` holds only `agent_public.pem`, `trust_registry.v1.json`, `trusted.json`. Tests call `_mint_ephemeral_principal()`, which generates an in-process Ed25519 keypair into a temp dir and enrolls it in a temp registry. No test reads developer-local private material. Two new tests were added (`TestSchemaFailClosed`, `test_seal_tree_sha_matches_head_tree`). CI will now be green.

### F-5 — Schema bypass — CLOSED as specified

`_schema_validate_file` gained `require_schema=True` and every dispatch path now passes it. The mandated check passes:

```
FAIL: Missing required $schema in mailbox\archive\wo-901-noschema.json
FAIL: Workorder missing issuer_signature: mailbox\archive\wo-901-noschema.json
```

Filename-based dispatch was replaced with `_classify_envelope()` content inspection. The Phase-1 forgery (`payload-996.json`, no `$schema`) is now rejected. See **R-1** for what the new dispatch still lets through.

### F-3 — Manifest source binding — CLOSED

Manifest grew from 11 entries (zero code) to **27 entries including all 15 `lib/wdd/*.py` files**: `__init__`, `__main__`, `canonical`, `cli`, `compiler`, `crypto`, `gate`, `ledger`, `mailbox`, `registry`, `replay`, `scheduler`, `sync`, `telemetry`, `validator`.

I verified every digest against the **attested git tree object** `c44e72ba`, not the working tree:

```
mismatches: NONE — all 27 bind to the attested tree
.py files in attested tree : 21
covered by manifest        : 15   (all of lib/)
uncovered                  : bootstrap.py, tools/*.py (2), tests/*.py (3)
```

The manifest is **cryptographically bound**, not merely adjacent. I confirmed this by tampering:

- Flipping one manifest digest → seal signature **REJECTED**
- Flipping `tree_sha` → seal signature **REJECTED**

`seal_evidence_digest` recomputes exactly, `wo-032` signature verifies, and the receipt's `evidence_digest_sha256` matches the seal.

### F-2 — Cyclic tree validation — CLOSED

```
HEAD              09a9631ae8c2b9305c7e95dadf0a076d4821e392
HEAD^  (attested) 122cd7db471b8ad32c166b5dd0f5482571d25a4e
HEAD^^{tree}      c44e72bae9e9a23824acc2f68798b851b7de49b4
wo-032.tree_sha   c44e72bae9e9a23824acc2f68798b851b7de49b4   ← exact match
```

The construction is sound. A commit cannot contain the OID of its own tree, so attesting the parent tree is the correct resolution. Critically, I verified the **seal commit touches only seal artifacts**:

```
ledger/000029_*.json, mailbox/archive/wo-032-genesis-seal.json,
mailbox/receipts/receipt_wo-032-genesis-seal.json
```

No source file changes ride along in the seal commit, so the attested tree `c44e72ba` contains exactly the code present at HEAD. The only unattested delta is the seal's own bookkeeping — which is unavoidable and self-evident.

I then attacked the invariant's two-candidate tolerance (`HEAD^{tree}` or `HEAD^^{tree}`), suspecting it was too permissive. **It is not.** Both drift scenarios were caught:

- Code change + extra commit → `test_seal_tree_sha_matches_head_tree` **FAILED** (correct)
- Single code-only commit on top of the seal → **FAILED** (correct)

Any commit after the seal shifts `HEAD^^{tree}` off the sealed value, so the invariant **self-tightens and forces a re-seal**. This is a stronger property than the workorder claimed.

Chain state: **30/30 ledger blocks verify**, head hash `4d893758…`.

## Residuals (non-blocking, disclosed)

### R-1 — MEDIUM — `.result.json` filename still short-circuits content dispatch

`_classify_envelope()` is documented as "content-based dispatch (not filename-based)", but its **first line is filename-based**:

```python
if name.endswith(".result.json"):
    return "result"          # → schema-only, signature never checked
```

`result.schema.json` requires only `workorder_id`, `status`, `outcome` with `additionalProperties: true`. Four forgeries passed `wdd validate`:

| Attack | Result |
|---|---|
| unsigned forgery as `wo-902-evil.result.json` | **PASS** |
| real signed result artifact, body tampered, signature kept | **PASS** |
| `workorder_id` only, no `action`/`assigned_to`/`issuer_signature` | **PASS** |
| **real workorder, signature stripped, renamed `.result.json`** | **PASS** |

The last is the meaningful one: filename still overrides content for exactly the class the fix set out to eliminate. Note also that `wo-000-genesis-audit.result.json` *carries* an `issuer_signature` that is **never verified** — an artifact that looks attested but is not.

**Not chain-exploitable.** With all four forgeries in place, `wdd replay --benchmark` still exits `0` — result artifacts never enter the ledger, and replay independently verifies every workorder signature. This is an admission-gate weakness in `validate`, not a break in the Genesis chain.

**Fix:** classify `.result.json` by content too, and either verify `issuer_signature` when present or strip it from result envelopes.

### R-2 — LOW — Nothing enforces the manifest against file bytes

No tool or test hashes the manifest's files and compares. `test_wo032_binds_tree_sha_and_manifest` checks only that the manifest exists, is self-consistent, is signed, and names `validator.py`/`gate.py`.

I appended a marker line to `lib/wdd/gate.py` — a manifest-covered verifier source — producing real digest drift:

```
manifest digest : 61ffc16aaa443ac1397b6e27893e00f9c7107afcb02612f56d8de06703b0348e
actual digest   : a14c200d07387198a28607a8732ebbe9fc5ecdcf7545e3a6b1cc5a8d83e0de16
```

Result: **16/16 tests pass, `validate` exit 0, `replay` exit 0.** Only `git status` noticed.

Scope is narrow: *committed* drift is caught by the cyclic invariant (proven above), and manifest corruption cannot be re-signed without the private key. The exposure is **uncommitted working-tree drift**. An external verifier — as I did here — can always recompute independently, so the attestation Iman receives is sound.

**Fix:** add `wdd verify-seal` that recomputes every manifest digest against the attested tree, and run it in CI.

### R-3 — Advisory — The manifest does not cover its own proof

`tests/*.py`, `tools/perfect_reseal.py`, `tools/remediate_genesis_binding.py`, and `bootstrap.py` are outside the seal. The adversarial suite that demonstrates the invariants is itself unsealed and could be weakened without breaking the seal. The workorder asked for `lib/wdd/*.py`, which is fully satisfied; extending coverage to `tests/` and `tools/` is a natural Phase 3 item.

### Carried forward from Phase 1 (unchanged, advisory)

- **F-7:** `trust_registry.v1.json` is unsigned; root of trust is the git tree itself.
- **F-8:** `wdd keygen` rotation does not auto-revoke the superseded key (fails closed, but no audit trail).
- **F-10:** all 30 receipts carry `token_burn: 0`, so the rubric ceiling is enforced but unexercised on live data.

## Final attestation values

```
HEAD commit           09a9631ae8c2b9305c7e95dadf0a076d4821e392
ATTESTED TREE SHA     c44e72bae9e9a23824acc2f68798b851b7de49b4   ← send this
HEAD tree             3b0a06822851561f39ff0d0ba1db17484ad125fc
seal_evidence_digest  2892249f256048eef935a31cecc5d61a5acd70c7a802cd1864dffc1a44b1afcf
wo-032 digest         4a8b1e1770e9d9706f1f7fc6ba59e4d7c73297a6c57e96cd02e22b3ef28cd097
receipt digest        f71da716fe1a76d70a05bbbf64e12a16a3133314b562cc3513241574f4d779f0
ledger head hash      4d893758c02a8839f00ac9219b516a53c68f67504b54a14e4fc41950757bf96b
ledger blocks         30
manifest entries      27  (15 lib/wdd/*.py)
```

**The SHA to send Dr. Schrock is `c44e72bae9e9a23824acc2f68798b851b7de49b4`** — the attested tree, reachable as `git rev-parse 09a9631^^{tree}`. It is the tree the seal signs, and the tree whose 27 manifest digests I independently reproduced from git objects.
