#!/usr/bin/env python3
"""
Phase-2 perfect reseal.

Git cannot store a tree OID inside a blob that is itself part of that tree
(self-reference). The mathematically honest seal therefore:

1. Commits all Phase-2 content first (caller does this), yielding tree T.
2. This script rebinds WO-032 to T, refreshes the tip receipt/ledger entry.
3. Caller commits the seal delta as the tip.

Invariant Claude must verify:
    wo-032.tree_sha == git rev-parse HEAD^^{tree}
when HEAD is the seal-tip commit (attests the content tree at HEAD~1).

If HEAD is the content commit itself (no seal-tip yet), tree_sha == HEAD^{tree}.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "tools"))

from remediate_genesis_binding import (  # noqa: E402
    GENESIS_ORDER,
    rebind_wo032,
    rebuild,
    reissue_receipts,
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    # Attest the current HEAD tree (content commit). Caller must have committed
    # Phase-2 fixes already so HEAD^{tree} is the tree under audit.
    tree = git("rev-parse", "HEAD^{tree}")
    print(f"Attesting HEAD tree: {tree}")
    rebind_wo032(tree_sha=tree)
    # Only tip receipt needs a new evidence digest; full reissue keeps chain coherent.
    reissue_receipts()
    rebuild()
    wo = json.loads(
        (ROOT / "mailbox" / "archive" / "wo-032-genesis-seal.json").read_text(
            encoding="utf-8"
        )
    )
    assert wo["tree_sha"] == tree, (wo["tree_sha"], tree)
    lib_keys = [k for k in wo["result_manifest"] if k.startswith("lib/wdd/")]
    assert "lib/wdd/validator.py" in lib_keys, lib_keys
    print(f"WO-032 rebound. lib/ files in manifest: {len(lib_keys)}")
    print(f"Genesis blocks: {len(GENESIS_ORDER)}")
    print("NEXT: git add seal artifacts && git commit -m 'seal(wo-032): attest HEAD tree'")
    print(f"THEN verify: git rev-parse HEAD^^{{tree}} == {tree}")


if __name__ == "__main__":
    main()
