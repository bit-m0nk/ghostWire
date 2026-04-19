"""GhostWire — Two-factor auth domain router re-export.

The implementation lives in twofa_router.py.  This shim lets the rest of
the codebase import from the conventional ``.router`` path without renaming
the original file.
"""
from .twofa_router import router  # noqa: F401
