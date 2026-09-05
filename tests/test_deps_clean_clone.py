"""Clean-clone dependency invariants for WO_20260905_001."""

from __future__ import annotations

import importlib.metadata
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

ROOT = Path(__file__).resolve().parents[1]


class TestCleanCloneDependencies(unittest.TestCase):
    def test_pyproject_declares_cryptography_and_jsonschema(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        deps = data["project"]["dependencies"]
        joined = "\n".join(deps)
        self.assertIn("cryptography", joined)
        self.assertIn("jsonschema", joined)

    def test_runtime_imports_resolve(self):
        import cryptography  # noqa: F401
        import jsonschema  # noqa: F401
        from wdd import cli, crypto, gate, ledger, replay, validator  # noqa: F401

        self.assertTrue(callable(cli.main))
        self.assertTrue(callable(validator.validate_all))
        self.assertTrue(callable(replay.replay_ledger))

    def test_installed_versions_readable(self):
        # Fresh install must expose these packages to metadata the same way BOL emitters do.
        self.assertNotEqual(importlib.metadata.version("cryptography"), "")
        self.assertNotEqual(importlib.metadata.version("jsonschema"), "")


if __name__ == "__main__":
    unittest.main()
