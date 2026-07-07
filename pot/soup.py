"""pot.soup — the open-ended primordial soup engine (Engine 1).

We seed a soup of tapes with pure random instructions, then repeat one rule:
shuffle, pair, concatenate, run each pair as a single BFF program, split the
result back into two tapes, write them back, and occasionally flip a random
byte. **There is no selection and no goal.** We only *watch* the soup for the
signature of a replicator — a program we never wrote — copying itself across the
population.

Everything here is *observed*, never optimized. The metrics exist to catch
emergence, not to cause it.

The scramble control (`ScrambleMode`) is a first-class citizen: it globally
permutes every byte in the soup at the start of each epoch, destroying any
genome or spatial correlation while preserving the exact byte histogram. It is
the null distribution for every metric below — if a metric fires just as hard on
the scrambled soup, the "signal" is an artifact of the metric, not emergence.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np

from . import run_batch, HAVE_RUST
from .bff import INSTRUCTION_SET

_IS = np.frombuffer(INSTRUCTION_SET, dtype=np.uint8)


@dataclass
class SoupConfig:
    soup_size: int = 512         # number of tapes in the soup
    tape_len: int = 64           # length L of each tape
    max_steps: int = 512         # BFF step budget per interaction (2L program)
    mut_per_tape: float = 1.0    # expected background mutations per tape per epoch
    epochs: int = 2000
    checkpoint_every: int = 50    # record metrics this often
    near_repl_sample: int = 128   # pairs sampled for the near-replication probe
    seed: int = 0
    scramble: bool = False        # if True, this is the structureless control


def _byte_entropy(cells: np.ndarray) -> float:
    """Shannon entropy (bits) of the byte-value distribution over all cells.

    Random init draws from a 10-symbol instruction set, so this starts near
    log2(10) ~= 3.32 bits and *collapses* when one genome sweeps the soup.
    """
    counts = np.bincount(cells.reshape(-1), minlength=256).astype(np.float64)
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-(p * np.log2(p)).sum())


def _top_motif_share(soup: np.ndarray, k: int = 8) -> float:
    """Share of the single most common k-mer across every tape in the soup.

    A replicator seeds one motif — its own genome — into many tapes, so the most
    common k-mer's share climbs far above the background even if no tape is an
    *exact* copy and diversity stays high (a quasispecies). The scrambled control
    destroys shared substrings, so this is control-gated: it is the substring
    analogue of ``top_share`` and catches replicators that ``repl_rate`` and the
    lineage-sweep miss.
    """
    N, L = soup.shape
    if L < k:
        return 0.0
    win = np.lib.stride_tricks.sliding_window_view(soup, k, axis=1)  # (N,L-k+1,k)
    flat = np.ascontiguousarray(win.reshape(-1, k))
    v = flat.view(np.dtype((np.void, k)))  # each k-mer as one hashable element
    _, counts = np.unique(v, return_counts=True)
    return float(counts.max()) / len(v)


def _best_shift_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Best fraction of matching positions between `a` and every cyclic shift
    of `b`. Catches a replicator that copied itself at an offset — a *partial*
    replicator invisible to an exact-equality check.
    """
    L = a.shape[0]
    best = 0.0
    for s in range(L):
        m = float(np.count_nonzero(a == np.roll(b, s))) / L
        if m > best:
            best = m
            if best == 1.0:
                break
    return best


@dataclass
class SoupRun:
    config: dict
    have_rust: bool
    trajectory: list = field(default_factory=list)   # list of checkpoint dicts
    dominant: list = field(default_factory=list)      # top genomes at the end
    fired: bool = False                               # did emergence fire (set by harness)

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self) if not isinstance(self.config, dict) else self.__dict__,
                      f, indent=2)


def run_soup(config: SoupConfig, progress: bool = False,
             checkpoint_path: Optional[str] = None) -> SoupRun:
    """Run the soup for ``config.epochs`` and return its trajectory.

    Deterministic in ``config.seed``. Checkpoints frequently so that a partial
    (interrupted) run still yields an honest trajectory. If ``checkpoint_path``
    is given, the growing :class:`SoupRun` is flushed to disk at every
    checkpoint.
    """
    rng = np.random.default_rng(config.seed)
    N, L = config.soup_size, config.tape_len
    P = N // 2  # pairs per epoch

    # Dense random init: every cell an instruction byte drawn uniformly.
    soup = _IS[rng.integers(0, len(_IS), size=(N, L))].astype(np.uint8)

    mut_rate = config.mut_per_tape / L if L else 0.0
    # rolling replication history so the reported rate is smoothed over epochs
    repl_window: deque = deque(maxlen=100)

    run = SoupRun(config=asdict(config), have_rust=HAVE_RUST)

    for epoch in range(config.epochs):
        if config.scramble:
            # Destroy all genome/spatial structure, keep the byte histogram.
            flat = soup.reshape(-1)
            rng.shuffle(flat)
            soup = flat.reshape(N, L)

        order = rng.permutation(N)
        ia = order[:P]
        ib = order[P:2 * P]

        a_before = soup[ia].copy()
        b_before = soup[ib].copy()

        # Concatenate each pair into one 2L program, run once per pair.
        joined = np.concatenate([a_before, b_before], axis=1)  # (P, 2L)
        pairs = [row.tobytes() for row in joined]
        results = run_batch(pairs, config.max_steps)

        res = np.frombuffer(b"".join(results), dtype=np.uint8).reshape(P, 2 * L)
        a_after = res[:, :L]
        b_after = res[:, L:]

        # Write mutated tapes back into the soup.
        soup[ia] = a_after
        soup[ib] = b_after

        # --- replication events this epoch (exact self-copy into the partner) ---
        differ = np.any(a_before != b_before, axis=1)
        b_is_copy_of_a = np.all(b_after == a_before, axis=1)
        a_is_copy_of_b = np.all(a_after == b_before, axis=1)
        events = np.count_nonzero(differ & (b_is_copy_of_a | a_is_copy_of_b))
        repl_window.append((events, P))

        # --- background mutation ---
        if mut_rate > 0:
            mask = rng.random((N, L)) < mut_rate
            k = int(mask.sum())
            if k:
                soup[mask] = _IS[rng.integers(0, len(_IS), size=k)]

        # --- checkpoint ---
        last = epoch == config.epochs - 1
        if last or (config.checkpoint_every and epoch % config.checkpoint_every == 0):
            # near-replication probe on a fresh sample of the just-run pairs
            ks = min(config.near_repl_sample, P)
            sample = rng.choice(P, size=ks, replace=False)
            sims = [_best_shift_similarity(a_after[s], b_after[s]) for s in sample]
            near_max = float(max(sims)) if sims else 0.0
            near_mean = float(np.mean(sims)) if sims else 0.0

            rows = np.ascontiguousarray(soup)
            uniq, counts = np.unique(rows.reshape(N, L), axis=0, return_counts=True)
            unique_ratio = len(uniq) / N
            top_share = float(counts.max()) / N

            r_events = sum(e for e, _ in repl_window)
            r_total = sum(t for _, t in repl_window)
            repl_rate = (r_events / r_total) if r_total else 0.0

            cp = {
                "epoch": epoch,
                "repl_rate": repl_rate,
                "unique_ratio": unique_ratio,
                "top_share": top_share,
                "entropy": _byte_entropy(soup),
                "near_repl_max": near_max,
                "near_repl_mean": near_mean,
                "motif_share": _top_motif_share(soup),
            }
            run.trajectory.append(cp)
            if checkpoint_path:
                # capture current dominant genomes so an interrupted run is honest
                order_c = np.argsort(-counts)[:5]
                run.dominant = [
                    {"genome": uniq[i].tobytes().hex(), "count": int(counts[i])}
                    for i in order_c
                ]
                with open(checkpoint_path, "w", encoding="utf-8") as f:
                    json.dump(run.__dict__, f, indent=2)
            if progress:
                print(f"  epoch {epoch:6d}  repl={repl_rate:.4f}  "
                      f"uniq={unique_ratio:.3f}  top={top_share:.3f}  "
                      f"H={cp['entropy']:.3f}  near={near_max:.3f}", flush=True)

    # final dominant genomes
    rows = np.ascontiguousarray(soup).reshape(N, L)
    uniq, counts = np.unique(rows, axis=0, return_counts=True)
    order_c = np.argsort(-counts)[:8]
    run.dominant = [
        {"genome": uniq[i].tobytes().hex(), "count": int(counts[i]),
         "ascii": _ascii(uniq[i])}
        for i in order_c
    ]
    if checkpoint_path:
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(run.__dict__, f, indent=2)
    return run


def _ascii(tape: np.ndarray) -> str:
    """Render a genome as printable BFF source (non-instruction bytes as '.')."""
    inst = set(INSTRUCTION_SET)
    return "".join(chr(b) if b in inst else "·" for b in tape.tolist())


# quantities the harness thresholds on
def summarize(run: SoupRun) -> dict:
    """Reduce a trajectory to the peak signals the verdict logic keys on."""
    if not run.trajectory:
        return {"peak_repl_rate": 0.0, "peak_near_repl": 0.0,
                "min_unique_ratio": 1.0, "max_top_share": 0.0,
                "min_entropy": 0.0, "final_entropy": 0.0, "peak_motif_share": 0.0}
    return {
        "peak_repl_rate": max(c["repl_rate"] for c in run.trajectory),
        "peak_near_repl": max(c["near_repl_max"] for c in run.trajectory),
        "min_unique_ratio": min(c["unique_ratio"] for c in run.trajectory),
        "max_top_share": max(c["top_share"] for c in run.trajectory),
        "min_entropy": min(c["entropy"] for c in run.trajectory),
        "final_entropy": run.trajectory[-1]["entropy"],
        "peak_motif_share": max(c.get("motif_share", 0.0) for c in run.trajectory),
    }
