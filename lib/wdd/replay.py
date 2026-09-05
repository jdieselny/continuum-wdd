"""Ledger replay with strict digest, receipt, and rubric enforcement."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from wdd.canonical import ledger_hash_payload
from wdd.gate import receipt_digest, verify_receipt_signature, verify_workorder_signature, workorder_digest
from wdd.ledger import get_hash_of_dict


class ReplayError(Exception):
    pass


def parse_iso(iso_str: str) -> datetime:
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1] + "+00:00"
    return datetime.fromisoformat(iso_str)


def _load_workorder(workorder_id: str) -> dict:
    candidates = [
        Path("mailbox/archive") / f"{workorder_id}.json",
        Path("mailbox/outbox") / f"{workorder_id}.json",
        Path("mailbox/inbox") / f"{workorder_id}.json",
        Path("workorders") / f"{workorder_id}.json",
    ]
    for path in candidates:
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise ReplayError(f"workorder artifact missing for {workorder_id}")


def _load_receipt(workorder_id: str, receipt_id: str) -> dict:
    candidates = [
        Path("mailbox/receipts") / f"receipt_{workorder_id}.json",
        Path("mailbox/receipts") / f"{receipt_id}.json",
        Path("mailbox/outbox") / f"receipt_{workorder_id}.json",
    ]
    for path in candidates:
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise ReplayError(f"receipt artifact missing for {workorder_id} / {receipt_id}")


def replay_ledger(benchmark: bool = False, ledger_dir: str | Path = "ledger") -> dict:
    ledger_path = Path(ledger_dir)
    if not ledger_path.exists():
        raise ReplayError("No ledger directory found.")

    entries = sorted(ledger_path.glob("*.json"))
    if not entries:
        raise ReplayError("Ledger is empty.")

    expected_prev = "0" * 64
    first_time = None
    last_time = None
    total_token_burn = 0

    print("WDD Replay: Verifying Hash Chain + Digests + Receipts...")
    for i, entry_path in enumerate(entries):
        with open(entry_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        prev_hash = data.get("previous_hash")
        if prev_hash != expected_prev:
            raise ReplayError(
                f"Hash chain broken at block {i}. Expected {expected_prev}, got {prev_hash}."
            )

        stored_current_hash = data.get("current_hash")
        recalculated_hash = get_hash_of_dict(ledger_hash_payload(data))
        if recalculated_hash != stored_current_hash:
            raise ReplayError(f"Block {i} current_hash does not match payload digest.")

        for required in ("workorder_digest", "receipt_digest", "workorder_id", "receipt_id"):
            if required not in data:
                raise ReplayError(f"Block {i} missing required field {required!r}.")

        workorder_id = data["workorder_id"]
        receipt_id = data["receipt_id"]

        workorder = _load_workorder(workorder_id)
        receipt = _load_receipt(workorder_id, receipt_id)

        verify_workorder_signature(workorder)
        verify_receipt_signature(receipt)

        wo_digest = workorder_digest(workorder)
        rcpt_digest = receipt_digest(receipt)
        if wo_digest != data["workorder_digest"]:
            raise ReplayError(
                f"Block {i} workorder_digest mismatch for {workorder_id}: "
                f"ledger={data['workorder_digest']} artifact={wo_digest}"
            )
        if rcpt_digest != data["receipt_digest"]:
            raise ReplayError(
                f"Block {i} receipt_digest mismatch for {receipt_id}: "
                f"ledger={data['receipt_digest']} artifact={rcpt_digest}"
            )

        token_burn = int(data.get("token_burn", receipt.get("token_burn", 0)) or 0)
        total_token_burn += token_burn

        issued_at = receipt.get("issued_at")
        if issued_at:
            t = parse_iso(issued_at)
            if first_time is None:
                first_time = t
            last_time = t

        expected_prev = stored_current_hash
        print(
            f"Verified: {workorder_id} -> {receipt_id} "
            f"(Hash: {stored_current_hash[:8]}... digest_ok)"
        )

    result = {
        "blocks": len(entries),
        "token_burn": total_token_burn,
        "wall_clock_seconds": 0.0,
    }

    if benchmark:
        rubric_path = Path("tests/rubric.json")
        if not rubric_path.exists():
            raise ReplayError("rubric.json not found.")
        with open(rubric_path, "r", encoding="utf-8") as f:
            rubric = json.load(f)

        max_time = rubric.get("max_wall_clock_seconds", 3600)
        max_tokens = rubric.get("max_token_burn")

        if first_time and last_time:
            delta = (last_time - first_time).total_seconds()
        else:
            delta = 0.0
        result["wall_clock_seconds"] = delta

        if delta > max_time:
            raise ReplayError(
                f"Execution time {delta}s exceeds rubric limit {max_time}s."
            )
        if max_tokens is not None and total_token_burn > int(max_tokens):
            raise ReplayError(
                f"Token burn {total_token_burn} exceeds rubric max_token_burn {max_tokens}."
            )

        print("PASS: Multi-record anchored replay successful.")
        print(f"PASS: Execution time: {delta:.2f}s (Limit: {max_time}s)")
        print(
            f"PASS: Token burn: {total_token_burn} "
            f"(Limit: {max_tokens if max_tokens is not None else 'n/a'})"
        )
        print("PASS: Benchmark score within rubric limits.")

    return result


def main_replay(benchmark: bool = False) -> None:
    try:
        replay_ledger(benchmark=benchmark)
    except ReplayError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
