"""the-pot — an accelerated origin-of-intelligence engine.

We build only the substrate physics. The soup is seeded with pure randomness.
There is no fitness function, no goal, and no replicator authored by us.
Whatever order emerges must be something we neither wrote nor can predict.

This package prefers the compiled Rust interpreter (``pot._rust``) and falls
back transparently to the pure-Python reference (``pot.bff``) when the
extension is not built. ``HAVE_RUST`` tells you which path is live.
"""

from __future__ import annotations

from . import bff
from .bff import INSTRUCTION_SET, run_tape, run_batch_py

try:  # pragma: no cover - exercised by whichever path is built
    from . import _rust  # type: ignore

    HAVE_RUST = True
    run_batch = _rust.run_batch
except Exception:  # noqa: BLE001 - any import failure means fall back
    HAVE_RUST = False
    run_batch = run_batch_py

__all__ = [
    "bff",
    "INSTRUCTION_SET",
    "run_tape",
    "run_batch",
    "run_batch_py",
    "HAVE_RUST",
]

__version__ = "0.1.0"
