"""pot.live — run a showcase soup and stream it to a watchable dashboard.

Runs one soup in the hot regime and, every checkpoint, writes ``web/live.json``:
the metric trajectory so far, a snapshot of the actual soup cells (so you can
watch the tapes move and, if it happens, a lineage sweep the grid into
uniformity), live rung indicators, and a phase-transition readout.
``web/live.html`` polls that file and animates it.

This is a *view*, not a verdict — it shows the real soup live; the
control-gated, honesty-checked results live in ``research/``.

Run:  python -m pot.live --soup-size 4096 --mut 0.1 --steps 1024 --epochs 200000
"""

from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from .soup import SoupConfig, run_soup, _ascii
from .observatory import phase_transitions, TRACKED

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "web", "live.json")

# absolute (not control-gated) indicators for the live view only; the rigorous
# control-gated verdicts are computed in the research pipeline, not here.
RUNGS = [
    ("self-replication", "repl_rate", 0.02),
    ("motif dominance", "motif_share", 0.12),
    ("lineage sweep", "top_share", 0.10),
]


def _atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, path)


def run_live(soup_size=4096, mut=0.1, steps=1024, epochs=200000, seed=0,
             checkpoint_every=40, grid_tapes=120, out=DEFAULT_OUT, low_priority=True):
    if low_priority:
        from .util import set_low_priority
        set_low_priority()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cfg = SoupConfig(soup_size=soup_size, tape_len=64, max_steps=steps,
                     mut_per_tape=mut, epochs=epochs,
                     checkpoint_every=checkpoint_every, seed=seed)
    t0 = time.time()
    regime = {"soup_size": soup_size, "tape_len": 64, "max_steps": steps,
              "mut_per_tape": mut, "epochs": epochs, "seed": seed}
    traj = []

    def snapshot(epoch, soup, cp, uniq, counts, status="running"):
        gt = min(grid_tapes, soup.shape[0])
        grid = soup[:gt].astype(int).tolist()          # real cells to render
        order = np.argsort(-counts)[:6]
        dominant = [{"count": int(counts[i]), "ascii": _ascii(uniq[i])} for i in order]
        rungs = [{"name": n, "metric": m, "value": round(cp.get(m, 0.0), 4),
                  "reached": bool(cp.get(m, 0.0) > thr), "threshold": thr}
                 for (n, m, thr) in RUNGS]
        elapsed = time.time() - t0
        eps = (len(traj) * checkpoint_every) / elapsed if elapsed > 0 else 0.0
        _atomic_write(out, {
            "status": status,
            "epoch": int(epoch), "total_epochs": epochs,
            "progress": round(epoch / epochs, 4) if epochs else 0.0,
            "elapsed_sec": round(elapsed, 1), "eps": round(eps, 1),
            "regime": regime,
            "trajectory": traj,
            "grid": grid, "grid_shape": [gt, int(soup.shape[1])],
            "dominant": dominant,
            "rungs": rungs,
            "phase_transitions": phase_transitions(traj, keys=TRACKED)[:6],
        })

    def cb(epoch, soup, cp, uniq, counts):
        traj.append(cp)
        snapshot(epoch, soup, cp, uniq, counts)

    print(f"[live] soup={soup_size} mut={mut} steps={steps} epochs={epochs} -> {out}")
    run = run_soup(cfg, on_checkpoint=cb)

    # mark the last written frame done (the soup snapshot in it is the final one)
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            final = json.load(f)
        final["status"] = "done"
        final["elapsed_sec"] = round(time.time() - t0, 1)
        _atomic_write(out, final)
    print(f"[live] done in {round(time.time() - t0, 1)}s, {len(traj)} frames")
    return run


def main(argv=None):
    ap = argparse.ArgumentParser(description="stream a showcase soup to web/live.json")
    ap.add_argument("--soup-size", type=int, default=4096)
    ap.add_argument("--mut", type=float, default=0.1)
    ap.add_argument("--steps", type=int, default=1024)
    ap.add_argument("--epochs", type=int, default=200000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--checkpoint-every", type=int, default=40)
    ap.add_argument("--grid-tapes", type=int, default=120)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--full-speed", action="store_true")
    args = ap.parse_args(argv)
    run_live(soup_size=args.soup_size, mut=args.mut, steps=args.steps,
             epochs=args.epochs, seed=args.seed,
             checkpoint_every=args.checkpoint_every, grid_tapes=args.grid_tapes,
             out=args.out, low_priority=not args.full_speed)


if __name__ == "__main__":
    main()
