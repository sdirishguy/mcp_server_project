"""
Backward‑compatibility shim for importing settings.

This module re‑exports the unified `settings` object from `app.config`.  It
exists to preserve imports like `from app.settings import settings` in
existing code and tests.
"""

from .config import settings  # noqa: F401
