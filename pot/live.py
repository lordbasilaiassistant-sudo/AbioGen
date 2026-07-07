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

from .soup import SoupConfig, run_soup, _ascii, _top_motif_share
from .observatory import phase_transitions, TRACKED

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "web", "live.json")

# absolute (not control-gated) indicators for the live view only; the rigorous
# control-gated verdicts are computed in the research pipeline, not here.
RUNGS = [
    ("self-replication", "repl_rate", 0.02, None),
    ("motif dominance", "motif_share", 0.12, "motif_control"),
    ("lineage sweep", "top_share", 0.10, "top_control"),
]


def _atomic_write(path, obj):
    # On Windows, OneDrive / the http server / a browser can briefly lock the
    # target, so os.replace races and raises WinError 5. Retry, then fall back to
    # a direct (non-atomic) write. A dropped live frame is harmless — the next
    # checkpoint overwrites it — so a lock must never crash the run.
    data = json.dumps(obj, separators=(",", ":"))
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        for _ in range(6):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                time.sleep(0.12)
        with open(path, "w", encoding="utf-8") as f:  # last-resort direct write
            f.write(data)
    except PermissionError:
        pass  # skip this frame entirely; the next one will land


def run_live(soup_size=4096, mut=0.1, steps=1024, epochs=200000, seed=0,
             checkpoint_every=40, grid_tapes=120, out=DEFAULT_OUT, low_priority=True,
             cosmic=False):
    if low_priority:
        from .util import set_low_priority
        set_low_priority()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    from . import cosmos
    seed, origin = cosmos.resolve_seed(seed, cosmic)   # real-physics origin, logged
    if origin:
        print(f"[live] cosmic seed {seed} from {origin['sources_live']} real sources")
    cfg = SoupConfig(soup_size=soup_size, tape_len=64, max_steps=steps,
                     mut_per_tape=mut, epochs=epochs,
                     checkpoint_every=checkpoint_every, seed=seed)
    t0 = time.time()
    regime = {"soup_size": soup_size, "tape_len": 64, "max_steps": steps,
              "mut_per_tape": mut, "epochs": epochs, "seed": seed}
    origin_summary = None
    if origin:
        origin_summary = {"sources_live": origin["sources_live"],
                          "sources": [p["source"] for p in origin["provenance"]
                                      if p["available"]]}
    traj = []

    def snapshot(epoch, soup, cp, uniq, counts, status="running"):
        N, L = soup.shape
        order = np.argsort(-counts)[:6]
        dominant = [{"count": int(counts[i]), "ascii": _ascii(uniq[i])} for i in order]

        # STRUCTURE MAP, not raw bytes: render each shown tape by how much it
        # matches the current dominant genome. A calm dark field lights up phosphor
        # exactly where order (a shared lineage) is taking hold — that is the thing
        # that matters, shown directly.
        gt = min(grid_tapes, N)
        dom = uniq[order[0]]
        window = soup[:gt]
        matchmap = (window == dom[None, :]).astype(np.uint8).tolist()

        # LIVE SCRAMBLED CONTROL: shuffle every byte (kills structure, keeps the
        # histogram) and recompute the order metrics on the wreckage. This is the
        # honest noise floor, computed on THIS soup, right now — the hero shows the
        # real soup pulling away from it, or not.
        shuf = soup.reshape(-1).copy()
        np.random.default_rng(int(epoch) + 1).shuffle(shuf)
        shuf = shuf.reshape(N, L)
        ctrl_motif = _top_motif_share(shuf)
        _, cc = np.unique(shuf, axis=0, return_counts=True)
        ctrl_top = float(cc.max()) / N
        cp["motif_control"] = round(ctrl_motif, 5)
        cp["top_control"] = round(ctrl_top, 5)

        rungs = [{"name": n, "metric": m, "value": round(cp.get(m, 0.0), 4),
                  "control": round(cp.get(ck, 0.0), 4) if ck else None,
                  "reached": bool(cp.get(m, 0.0) > thr), "threshold": thr}
                 for (n, m, thr, ck) in RUNGS]
        elapsed = time.time() - t0
        eps = (len(traj) * checkpoint_every) / elapsed if elapsed > 0 else 0.0
        _atomic_write(out, {
            "status": status,
            "epoch": int(epoch), "total_epochs": epochs,
            "progress": round(epoch / epochs, 4) if epochs else 0.0,
            "elapsed_sec": round(elapsed, 1), "eps": round(eps, 1),
            "regime": regime, "origin": origin_summary,
            "trajectory": traj,
            "matchmap": matchmap, "grid_shape": [gt, int(L)],
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
    ap.add_argument("--cosmic-seed", action="store_true",
                    help="seed this world from real physical entropy (logged)")
    args = ap.parse_args(argv)
    run_live(soup_size=args.soup_size, mut=args.mut, steps=args.steps,
             epochs=args.epochs, seed=args.seed,
             checkpoint_every=args.checkpoint_every, grid_tapes=args.grid_tapes,
             out=args.out, low_priority=not args.full_speed, cosmic=args.cosmic_seed)


if __name__ == "__main__":
    main()
