"""Hash-chained ledger with exact workorder/receipt digest binding."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from wdd.canonical import canonical_json_bytes, digest_obj, ledger_hash_payload
from wdd.gate import receipt_digest, workorder_digest


def get_hash_of_file(filepath) -> str:
    """Legacy helper retained for tooling; chain links no longer use raw file bytes."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_hash_of_dict(d: Mapping[str, Any]) -> str:
    return digest_obj(d)


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def append_entry(workorder: Mapping[str, Any], receipt: Mapping[str, Any], ledger_dir: str | Path = "ledger"):
    """
    Append a ledger entry bound to the exact workorder and receipt digests.

    Chain link is previous entry's current_hash (content digest), never raw
    file bytes — so CRLF/LF checkout differences cannot break replay.
    """
    ledger_path = Path(ledger_dir)
    ledger_path.mkdir(parents=True, exist_ok=True)

    entries = sorted(ledger_path.glob("*.json"))
    if not entries:
        previous_hash = "0" * 64
    else:
        with open(entries[-1], "r", encoding="utf-8") as f:
            last = json.load(f)
        previous_hash = last["current_hash"]

    entry_data = {
        "previous_hash": previous_hash,
        "workorder_id": workorder.get("workorder_id", ""),
        "receipt_id": receipt.get("receipt_id", ""),
        "workorder_digest": workorder_digest(workorder),
        "receipt_digest": receipt_digest(receipt),
        "token_burn": int(
            receipt.get("token_burn", workorder.get("token_projection", 0)) or 0
        ),
    }
    entry_data["current_hash"] = get_hash_of_dict(ledger_hash_payload(entry_data))

    new_entry_filename = f"{len(entries):06d}_{entry_data['current_hash'][:8]}.json"
    new_entry_path = ledger_path / new_entry_filename
    _write_json(new_entry_path, entry_data)
    return new_entry_path


def rebuild_ledger(
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]],
    ledger_dir: str | Path = "ledger",
) -> list[Path]:
    """Erase and rebuild the ledger from ordered (workorder, receipt) pairs."""
    ledger_path = Path(ledger_dir)
    ledger_path.mkdir(parents=True, exist_ok=True)
    for old in ledger_path.glob("*.json"):
        old.unlink()
    written: list[Path] = []
    for workorder, receipt in pairs:
        written.append(append_entry(workorder, receipt, ledger_dir=ledger_path))
    return written
