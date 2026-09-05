import json
import subprocess
import sys
import hashlib
from typing import Dict

from wdd.gate import verify_workorder_signature

def _git_cat_file(tree_sha: str, path: str) -> bytes:
    cmd = ["git", "cat-file", "-p", f"{tree_sha}:{path}"]
    res = subprocess.run(cmd, capture_output=True, check=False)
    if res.returncode != 0:
        raise ValueError(f"Git object {tree_sha}:{path} not found")
    return res.stdout

def _git_rev_parse(rev: str) -> str:
    cmd = ["git", "rev-parse", rev]
    res = subprocess.run(cmd, capture_output=True, check=False, text=True)
    if res.returncode != 0:
        raise ValueError(f"Git rev-parse failed for {rev}")
    return res.stdout.strip()

def verify_seal(seal_path: str = "mailbox/archive/wo-032-genesis-seal.json") -> bool:
    try:
        with open(seal_path, "r", encoding="utf-8") as f:
            seal_wo = json.load(f)
    except Exception as e:
        print(f"FAIL: Could not load seal workorder at {seal_path}: {e}")
        return False
        
    print(f"Loaded seal: {seal_wo.get('workorder_id')}")

    # 1. Verify cryptographic signature of the workorder
    try:
        verify_workorder_signature(seal_wo)
        print("PASS: Cryptographic signature verified.")
    except Exception as e:
        print(f"FAIL: Seal signature verification failed: {e}")
        return False

    tree_sha = seal_wo.get("tree_sha")
    if not tree_sha:
        print("FAIL: No tree_sha found in seal.")
        return False
        
    print(f"Seal attested tree: {tree_sha}")

    # 2. Check cyclic tree invariant (wo.tree_sha == HEAD^{tree} or HEAD^^{tree})
    try:
        head_tree = _git_rev_parse("HEAD^{tree}")
        head_parent_tree = _git_rev_parse("HEAD^^{tree}")
        
        if tree_sha != head_tree and tree_sha != head_parent_tree:
            print(f"FAIL: Cyclic invariant broken! Attested {tree_sha} matches neither HEAD^{{tree}} ({head_tree}) nor HEAD^^{{tree}} ({head_parent_tree})")
            return False
        else:
            match_str = "HEAD^{tree}" if tree_sha == head_tree else "HEAD^^{tree}"
            print(f"PASS: Cyclic tree invariant holds ({tree_sha} == {match_str}).")
    except Exception as e:
        print(f"FAIL: Git revision parsing failed: {e}")
        return False

    # 3. Recompute manifest hashes from the exact git tree (not working directory)
    manifest = seal_wo.get("result_manifest", {})
    if not manifest:
        print("FAIL: No result_manifest found.")
        return False

    print(f"Verifying {len(manifest)} manifest entries against attested tree...")
    failures = 0
    for file_path, expected_digest in manifest.items():
        try:
            content = _git_cat_file(tree_sha, file_path)
            # Normalization as per generate_evidence_digest if necessary, though git stores blobs with LF
            # Wait, git blobs are stored exactly as added. The evidence digest normalization was for file reads, 
            # but git blobs should hash perfectly. Let's try raw bytes first.
            # Actually, generate_evidence_digest in gate.py normalizes \r\n to \n.
            normalized = content.replace(b"\r\n", b"\n")
            actual_digest = hashlib.sha256(normalized).hexdigest()
            if actual_digest != expected_digest:
                print(f"  FAIL: {file_path} - expected {expected_digest}, got {actual_digest}")
                failures += 1
        except Exception as e:
            print(f"  FAIL: {file_path} - error reading from tree: {e}")
            failures += 1

    if failures > 0:
        print(f"FAIL: {failures} manifest entries mismatched.")
        return False

    print("PASS: All manifest digests verified against the attested git tree.")
    return True
