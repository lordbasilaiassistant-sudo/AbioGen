"""pot.util — small cross-platform helpers.

The one that matters here: :func:`set_low_priority`, so long local runs are
*polite*. Workers drop themselves to below-normal / idle scheduling priority, so
the OS hands foreground apps (a game, a browser) the CPU the instant they want
it, and the soup only fills the spare cycles. This is how we run heavy sweeps on
a machine that is also being used, without lag.
"""

from __future__ import annotations

import os
import sys


def set_low_priority(idle: bool = False) -> bool:
    """Lower the current process's scheduling priority. Returns True on success.

    Windows: BELOW_NORMAL (or IDLE) priority class via the Win32 API.
    POSIX:   ``os.nice`` (10, or 19 for idle).
    """
    try:
        if sys.platform == "win32":
            import ctypes
            BELOW_NORMAL = 0x00004000
            IDLE = 0x00000040
            # IMPORTANT (Win64): declare restype/argtypes explicitly. Otherwise
            # GetCurrentProcess() returns a 32-bit c_int and the 64-bit
            # pseudo-handle (-1) is truncated, so SetPriorityClass gets a bad
            # handle and silently fails.
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.GetCurrentProcess.restype = ctypes.c_void_p
            k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            k.SetPriorityClass.restype = ctypes.c_bool
            h = k.GetCurrentProcess()
            return bool(k.SetPriorityClass(h, IDLE if idle else BELOW_NORMAL))
        else:
            os.nice(19 if idle else 10)
            return True
    except Exception:  # noqa: BLE001 - politeness is best-effort, never fatal
        return False


def polite_worker_count(reserve_fraction: float = 0.5, minimum: int = 2) -> int:
    """A worker count that deliberately leaves cores free for the user.

    Defaults to using about half the logical cores (rounded down), never fewer
    than ``minimum``. On a 16-thread laptop that is ~8 workers at below-normal
    priority — heavy enough to make progress, light enough to disappear behind
    whatever else is running.
    """
    n = os.cpu_count() or 4
    return max(minimum, int(n * (1.0 - reserve_fraction)))
