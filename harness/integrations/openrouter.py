"""Resolve OpenRouter client from repo `src/` for both editable and pytest runs."""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
_src = _root / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from openrouter import OpenRouterClient  # noqa: E402

__all__ = ["OpenRouterClient"]
