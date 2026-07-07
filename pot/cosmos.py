"""pot.cosmos — bind the soup to the real universe's physics.

AbioGen normally seeds its worlds from a chosen integer. This module lets a world
instead draw its first breath from *actual physical indeterminism* harvested off
the machine and, when reachable, from a physics lab's live randomness — so the
origin of an AbioGen cosmos traces to the real one's noise, not to a formula.

The honesty discipline is intact: we harvest the physical entropy once, derive a
seed, and **log the seed and its provenance**, so a "cosmic" run is still
perfectly reproducible from its recorded seed — its *origin* is physical, its
record is deterministic. (A future `live_physics` mode that couples the soup to
the machine's ongoing state every epoch would be non-reproducible by design; it
is deliberately NOT what `cosmic_seed` does.)

What this does and does not do, stated plainly:
  * It makes a world's ORIGIN real — a genuine thread from physical noise.
  * It does NOT, on its own, make organisms "know" the world — noise is noise
    whether it comes from a thermometer or a PRNG. Binding organisms to real
    *structure* needs a real *signal* fed into their environment (the shared
    channel, issue #14) — `physical_sample()` is the first foundation for that.

Sources, each a graceful adapter that reports its own availability:
  * hardware entropy   — os.urandom / the OS pool (thermal + timing jitter; on
                         Intel, RDRAND samples on-die thermal noise). Always on.
  * timing jitter      — nanosecond deltas of the real clock. Always on.
  * machine state      — psutil: per-core load, live CPU frequency, memory,
                         battery — the real thermodynamic/operational state.
  * quantum / atmospheric — best-effort: a physics lab's public randomness beacon
                         (NIST) and atmospheric radio noise (random.org).
  * microphone / camera — real acoustic pressure / real photons (+ cosmic-ray
                         hits in sensor noise). OFF by default: needs the library
                         AND explicit opt-in (privacy — your mic/camera).
"""

from __future__ import annotations

import hashlib
import os
import time


# --------------------------------------------------------------------------- #
# individual real-world sources
# --------------------------------------------------------------------------- #
def _src_hardware_entropy():
    """OS entropy pool: fed by hardware thermal/timing noise. Always available."""
    return True, os.urandom(64), "os hardware entropy pool (thermal/timing)"


def _src_timing_jitter(samples: int = 512):
    """Nanosecond jitter of the real clock — genuine physical timing noise."""
    t = time.perf_counter_ns
    prev = t()
    acc = bytearray()
    for _ in range(samples):
        now = t()
        acc.append((now - prev) & 0xFF)
        prev = now
    return True, bytes(acc), f"clock jitter ({samples} ns-deltas)"


def _src_machine_state():
    """The real physical/operational state of this machine right now (psutil)."""
    try:
        import psutil
    except Exception:  # noqa: BLE001
        return False, b"", "psutil not installed"
    parts = []
    try:
        parts.append(str(psutil.cpu_percent(percpu=True)))
        f = psutil.cpu_freq()
        parts.append(str(f.current if f else ""))
        vm = psutil.virtual_memory()
        parts.append(f"{vm.percent}:{vm.available}")
        parts.append(str(psutil.swap_memory().used))
        b = psutil.sensors_battery()
        if b:
            parts.append(f"{b.percent}:{b.secsleft}")
        io = psutil.net_io_counters()
        parts.append(f"{io.bytes_sent}:{io.bytes_recv}")
        parts.append(str(time.time_ns()))
    except Exception:  # noqa: BLE001
        pass
    data = "|".join(parts).encode()
    if not data:
        return False, b"", "machine state unreadable"
    return True, data, "machine state (load/freq/mem/battery/net)"


def _src_nist_beacon(timeout: float = 3.0):
    """NIST public randomness beacon — a lab entropy source, signed + timestamped."""
    try:
        import requests
        r = requests.get("https://beacon.nist.gov/beacon/2.0/pulse/last",
                         timeout=timeout)
        val = r.json()["pulse"]["outputValue"]
        return True, bytes.fromhex(val), "NIST randomness beacon (lab entropy)"
    except Exception:  # noqa: BLE001
        return False, b"", "NIST beacon unreachable"


def _src_random_org(timeout: float = 3.0, n: int = 64):
    """random.org — genuine atmospheric radio noise (keyless plaintext API)."""
    try:
        import requests
        url = (f"https://www.random.org/integers/?num={n}&min=0&max=255"
               f"&col=1&base=10&format=plain&rnd=new")
        r = requests.get(url, timeout=timeout)
        vals = [int(x) for x in r.text.split()]
        if not vals:
            return False, b"", "random.org empty"
        return True, bytes(v & 0xFF for v in vals), "random.org (atmospheric noise)"
    except Exception:  # noqa: BLE001
        return False, b"", "random.org unreachable"


def _src_microphone(*_a, **_k):
    """Real acoustic pressure. OFF unless sounddevice present AND explicitly enabled."""
    return False, b"", "microphone (opt-in; sounddevice not enabled)"


def _src_camera(*_a, **_k):
    """Real photons + cosmic-ray sensor hits. OFF unless cv2 present AND opted in."""
    return False, b"", "camera (opt-in; cv2 not enabled)"


# always-on local physics + best-effort network physics
_LOCAL = [_src_hardware_entropy, _src_timing_jitter, _src_machine_state]
_NETWORK = [_src_nist_beacon, _src_random_org]


# --------------------------------------------------------------------------- #
# harvesting
# --------------------------------------------------------------------------- #
def harvest(network: bool = True, mic: bool = False, camera: bool = False):
    """Mix every available real-world source into a strong digest + provenance.

    Returns (digest_bytes, provenance) where provenance lists each source, whether
    it contributed, how many bytes, and a human note — so a run records exactly
    which pieces of the real universe seeded it.
    """
    sources = list(_LOCAL)
    if network:
        sources += _NETWORK
    if mic:
        sources.append(_src_microphone)
    if camera:
        sources.append(_src_camera)

    h = hashlib.sha512()
    provenance = []
    for fn in sources:
        ok, data, note = fn()
        if ok and data:
            h.update(data)
        provenance.append({"source": fn.__name__.replace("_src_", ""),
                           "available": bool(ok and data),
                           "bytes": len(data) if ok else 0, "note": note})
    # fold in a final os.urandom so the digest is never weaker than the OS pool
    h.update(os.urandom(32))
    return h.digest(), provenance


def cosmic_seed(bits: int = 64, network: bool = True, mic: bool = False,
                camera: bool = False):
    """A true-physical seed (+ provenance) for reproducible logging.

    The seed is drawn from real physics; because we return and log it, the run it
    seeds is still fully reproducible — its origin is the universe, its record is
    deterministic.
    """
    digest, provenance = harvest(network=network, mic=mic, camera=camera)
    seed = int.from_bytes(digest[: max(8, bits // 8)], "big") & ((1 << bits) - 1)
    live = sum(1 for p in provenance if p["available"])
    return seed, {"seed": seed, "bits": bits, "sources_live": live,
                  "provenance": provenance}


def resolve_seed(seed: int, cosmic: bool, network: bool = True):
    """One resolver every entry point shares: return (seed, origin).

    If ``cosmic``, the seed is drawn from real physics and ``origin`` records its
    provenance (for logging / display). Otherwise the given integer seed is used
    and ``origin`` is None. Either way the returned seed is what gets logged, so
    the run reproduces.
    """
    if not cosmic:
        return seed, None
    cseed, origin = cosmic_seed(network=network)
    return cseed, origin


def physical_sample(n: int = 64):
    """A real-world signal vector for future environment coupling (issue #14).

    Turns live physical state (timing microstructure + machine state entropy) into
    n bytes of *structured* real-world signal — the seed of a channel organisms
    could one day read. Foundation only; not yet wired into the soup.
    """
    import numpy as np
    _, jitter, _ = _src_timing_jitter(samples=n)
    ok, state, _ = _src_machine_state()
    buf = bytearray(jitter[:n])
    if ok and state:
        sh = hashlib.sha512(state).digest()
        for i in range(len(buf)):
            buf[i] ^= sh[i % len(sh)]
    return np.frombuffer(bytes(buf), dtype=np.uint8).copy()


def describe(network: bool = True) -> str:
    """One-line-per-source readout of what real-world physics is reachable now."""
    _, prov = harvest(network=network)
    lines = ["real-world sources:"]
    for p in prov:
        mark = "OK " if p["available"] else "-- "
        lines.append(f"  {mark}{p['source']:16} {p['note']}"
                     + (f"  ({p['bytes']}B)" if p["available"] else ""))
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
    seed, meta = cosmic_seed()
    print(f"\ncosmic seed: {seed}  ({meta['sources_live']} live sources)")
