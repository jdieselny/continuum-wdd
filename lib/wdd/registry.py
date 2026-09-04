"""
Action Registry
Defines the canonical list of actions the fleet is allowed to execute.
Implements a deny-by-default allowlist of acceptable action verbs.
"""

from typing import Set

ALLOWED_ACTIONS: Set[str] = {
    "trust.crypto.keygen",
    "cli.engine.sweep",
    "trust.sandbox.registry",
}

def is_action_allowed(action: str) -> bool:
    """
    Check if a given action verb is in the allowlist.
    """
    return action in ALLOWED_ACTIONS
