#!/usr/bin/env python3
"""
WO_20260905_001 remediation helper.

Re-signs every workorder over the full canonical object, rebinds WO-032 to the
exact git tree SHA + result manifest, re-issues receipts, and rebuilds the
ledger with workorder/receipt digest binding.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from wdd.canonical import canonical_json_bytes, digest_obj  # noqa: E402
from wdd.gate import (  # noqa: E402
    generate_evidence_digest,
    issue_receipt,
    sign_workorder,
)
from wdd.ledger import rebuild_ledger  # noqa: E402


ARCHIVE = ROOT / "mailbox" / "archive"
INBOX = ROOT / "mailbox" / "inbox"
RECEIPTS = ROOT / "mailbox" / "receipts"
LEDGER = ROOT / "ledger"

# Preserve genesis ledger order from the prior hash-chained run.
GENESIS_ORDER = [
    "wo-000-genesis-audit",
    "wo-001-cli-init",
    "wo-002-intent-processor",
    "wo-003-ob-writer",
    "wo-004-telemetry-dashboard",
    "wo-005-mailbox-sweep",
    "wo-006-schema-workorder",
    "wo-007-stage0-bootstrap",
    "wo-008-packaging",
    "wo-009-lifecycle",
    "wo-010-schema-ledger",
    "wo-011-schema-telemetry",
    "wo-012-schema-agent",
    "wo-013-wdd-validate",
    "wo-014-mailbox-contract",
    "wo-015-signed-inbound",
    "wo-016-keygen",
    "wo-017-action-registry",
    "wo-018-receipt-gate",
    "wo-019-replay-defense",
    "wo-020-dead-letter",
    "wo-021-ledger-recorder",
    "wo-022-wdd-replay",
    "wo-023-benchmark-rubric",
    "wo-024-holemap-sync",
    "wo-025-topological-scheduler",
    "wo-026-telemetry-emitter",
    "wo-029-namespace-decision",
    "wo-031-prompt-persistence",
    "wo-032-genesis-seal",
]


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_result_manifest() -> dict[str, str]:
    """Digest map for the Genesis Seal deliverables and core contracts."""
    import hashlib

    paths = [
        "docs/GENESIS_SEAL.md",
        "docs/HOLEMAP.md",
        "docs/AUDIT_REPORT.md",
        "docs/INTENT.md",
        "schemas/workorder.schema.json",
        "schemas/receipt.schema.json",
        "schemas/ledger.schema.json",
        "keys/trust_registry.v1.json",
        "tests/rubric.json",
        "pyproject.toml",
        "README.md",
    ]
    manifest: dict[str, str] = {}
    for rel in paths:
        path = ROOT / rel
        if path.is_file():
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            manifest[rel] = hashlib.sha256(raw).hexdigest()
    return manifest


def seal_evidence_digest(tree_sha: str, result_manifest: dict) -> str:
    return digest_obj({"tree_sha": tree_sha, "result_manifest": result_manifest})


def rebind_wo032(tree_sha: str | None = None) -> Path:
    path = ARCHIVE / "wo-032-genesis-seal.json"
    wo = load_json(path)
    # Drop prior signature before mutating bound fields
    wo.pop("issuer_signature", None)

    if tree_sha is None:
        # Prefer the git index tree so the seal can be refreshed after staging.
        try:
            tree_sha = git_output("write-tree")
        except subprocess.CalledProcessError:
            tree_sha = git_output("rev-parse", "HEAD")

    result_manifest = build_result_manifest()
    evidence = seal_evidence_digest(tree_sha, result_manifest)

    wo["tree_sha"] = tree_sha
    wo["result_manifest"] = result_manifest
    wo["result_manifest_digest"] = digest_obj(result_manifest)
    wo["seal_evidence_digest"] = evidence
    wo["status"] = "SEALED"
    wo["description"] = (
        "The system has successfully bootstrapped itself. This workorder binds the "
        f"exact git tree SHA {tree_sha} and the result manifest; evidence digest "
        f"{evidence} must match the EP-RECEIPT."
    )

    wo = sign_workorder(wo, key_id="principal_agent_smith")
    write_json(path, wo)
    return path


def resign_all_workorders() -> list[Path]:
    paths: list[Path] = []
    for folder in (ARCHIVE, INBOX):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("wo-*.json")):
            if path.name == "wo-032-genesis-seal.json":
                continue
            wo = load_json(path)
            wo.pop("issuer_signature", None)
            if "token_projection" not in wo:
                wo["token_projection"] = 0
            wo = sign_workorder(wo, key_id="principal_agent_smith")
            write_json(path, wo)
            paths.append(path)
    return paths


def reissue_receipts(preserve_timestamps: bool = True) -> dict[str, dict]:
    """Re-issue receipts; optionally keep original issued_at for wall-clock continuity."""
    original_times: dict[str, str] = {}
    if preserve_timestamps and RECEIPTS.is_dir():
        for path in RECEIPTS.glob("receipt_*.json"):
            data = load_json(path)
            if "issued_at" in data and "workorder_id" in data:
                original_times[data["workorder_id"]] = data["issued_at"]

    receipts: dict[str, dict] = {}
    for wo_id in GENESIS_ORDER:
        wo_path = ARCHIVE / f"{wo_id}.json"
        if not wo_path.is_file():
            raise FileNotFoundError(wo_path)

        wo = load_json(wo_path)
        if wo_id == "wo-032-genesis-seal":
            evidence = wo["seal_evidence_digest"]
        else:
            evidence = generate_evidence_digest(str(wo_path))

        extra = {"token_burn": int(wo.get("token_projection", 0) or 0)}
        out = issue_receipt(
            str(wo_path),
            evidence_digest=evidence,
            extra_fields=extra,
        )
        receipt = load_json(Path(out))
        if wo_id in original_times:
            # Re-sign after restoring the historical timestamp so wall-clock stays meaningful.
            receipt.pop("signature", None)
            receipt["issued_at"] = original_times[wo_id]
            # Re-issue via gate helpers
            from wdd.gate import load_private_key, sign_payload
            from wdd.canonical import canonical_json_bytes

            priv = load_private_key()
            sig_b64 = sign_payload(priv, canonical_json_bytes(receipt))
            receipt["signature"] = {
                "key_id": "agent_key",
                "alg": "Ed25519",
                "sig_b64": sig_b64,
            }
            write_json(Path(out), receipt)
        receipts[wo_id] = receipt
        print(f"Re-issued receipt for {wo_id}")
    return receipts


def rebuild() -> None:
    pairs = []
    for wo_id in GENESIS_ORDER:
        wo = load_json(ARCHIVE / f"{wo_id}.json")
        receipt = load_json(RECEIPTS / f"receipt_{wo_id}.json")
        pairs.append((wo, receipt))
    written = rebuild_ledger(pairs, ledger_dir=LEDGER)
    print(f"Rebuilt {len(written)} ledger entries")


def main() -> None:
    print("== Resigning workorders (full canonical binding) ==")
    resign_all_workorders()
    print("== Rebinding WO-032 to tree SHA + result manifest ==")
    rebind_wo032()
    print("== Re-issuing receipts ==")
    reissue_receipts()
    print("== Rebuilding ledger with digest binding ==")
    rebuild()
    # Refresh WO-032 against post-rebuild tree and rewrite final ledger entry set
    print("== Refreshing WO-032 after ledger rebuild ==")
    rebind_wo032()
    reissue_receipts()
    rebuild()
    print("DONE")


if __name__ == "__main__":
    main()
