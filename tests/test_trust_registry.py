"""Trust registry + gitignore invariants."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestTrustRegistryAndGitignore(unittest.TestCase):
    def test_root_gitignore_blocks_private_keys(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("*_private.pem", text)
        self.assertIn("keys/*_private.pem", text)

    def test_keys_gitignore_blocks_private_but_allows_registry(self):
        text = (ROOT / "keys" / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("*_private.pem", text)
        self.assertIn("!trust_registry.v1.json", text)

    def test_trust_registry_ships_and_revokes_old_key(self):
        from wdd.crypto import is_revoked_pem, load_trust_registry

        registry = load_trust_registry(str(ROOT / "keys" / "trust_registry.v1.json"))
        self.assertEqual(registry["version"], 1)
        self.assertIn("agent_key", registry["keys"])
        self.assertEqual(registry["keys"]["agent_key"]["status"], "ACTIVE")
        self.assertTrue(registry["revoked"])

        old_pem = (
            "-----BEGIN PUBLIC KEY-----\n"
            "MCowBQYDK2VwAyEAFkZg20L4ueLoqydE0K2NAFRksB1z/uuzJbqy7+gmgqg=\n"
            "-----END PUBLIC KEY-----\n"
        )
        self.assertTrue(
            any(r.get("public_key_pem") == old_pem for r in registry["revoked"])
        )
        self.assertTrue(is_revoked_pem(old_pem, str(ROOT / "keys" / "trust_registry.v1.json")))
        self.assertEqual(
            registry["revoked"][0].get("historical_commit"),
            "6bf5b1049412362ede2a2d3863f55f6558709674",
        )


if __name__ == "__main__":
    unittest.main()
