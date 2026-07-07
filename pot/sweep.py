"""pot.sweep — broad parameter sweep for the open-ended soup, across all cores.

The single-run interpreter is already fast, but the *question* — does a
replicator emerge, and where in parameter space — needs many long runs. This
module fans a grid of (tape_len x max_steps x mut_per_tape x soup_size) x seeds
across every core as independent single-threaded workers (each Rust call pinned
to one rayon thread via ``RAYON_NUM_THREADS=1``), which benchmarks faster than
one rayon-parallel run at this batch size.

Each grid cell is paired with its scrambled control, exactly as in
``pot.experiment`` — the honesty gate travels with the sweep. The output is a
compact per-cell fire table plus the full trajectory of the single most-ordered
real run (and its control) for the frontend hero.

Run:  ``python -m pot.sweep --epochs 50000 --seeds 6``
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict


# ---- default grid -----------------------------------------------------------
# mut_per_tape is the axis most likely to gate emergence: too low and the soup
# is frozen, too high and any replicator drowns in error catastrophe.
DEFAULT_GRID = {
    "tape_len": [64, 128],
    "max_steps": [256, 512, 1024],
    "mut_per_tape": [0.25, 1.0, 4.0],
    "soup_size": [512],
}


def _cells(grid):
    from itertools import product
    keys = list(grid.keys())
    for combo in product(*[grid[k] for k in keys]):
        yield dict(zip(keys, combo))


def _init_worker():
    """Pool initializer: make every worker polite (below-normal priority)."""
    from .util import set_low_priority
    set_low_priority()


def _worker(task):
    """Run one (cell, seed): real + scrambled control. Module-level for spawn."""
    # imported inside the worker so RAYON_NUM_THREADS (set by the parent env) is
    # honored when rayon initializes its pool.
    from .soup import SoupConfig, run_soup, summarize
    from .experiment import _fires, _near_watch

    cell, seed, epochs, checkpoint_every = task
    real_cfg = SoupConfig(seed=seed, epochs=epochs, checkpoint_every=checkpoint_every,
                          scramble=False, **cell)
    ctrl_cfg = SoupConfig(seed=seed, epochs=epochs, checkpoint_every=checkpoint_every,
                          scramble=True, **cell)
    real = run_soup(real_cfg)
    ctrl = run_soup(ctrl_cfg)
    rs, ks = summarize(real), summarize(ctrl)
    fired, reasons = _fires(rs, ks)
    return {
        "cell": cell,
        "seed": seed,
        "real": rs,
        "control": ks,
        "fired": fired,
        "reasons": reasons,
        "near_watch": _near_watch(rs, ks),
        "real_trajectory": real.trajectory,
        "control_trajectory": ctrl.trajectory,
        "dominant": real.dominant,
    }


def run_sweep(grid=None, seeds=6, epochs=50000, checkpoint_every=500,
              workers=None, out="sweep_results.json", progress=True):
    from .util import set_low_priority, polite_worker_count
    os.environ["RAYON_NUM_THREADS"] = "1"  # inherited by spawned workers
    set_low_priority()  # the parent, too
    grid = grid or DEFAULT_GRID
    cells = list(_cells(grid))
    tasks = [(c, s, epochs, checkpoint_every) for c in cells for s in range(seeds)]
    # Polite by default: leave half the cores for the user, below-normal priority.
    workers = workers or polite_worker_count()

    print(f"[sweep] {len(cells)} cells x {seeds} seeds = {len(tasks)} runs "
          f"(+ {len(tasks)} scrambled controls), {epochs} epochs each, "
          f"{workers} polite workers (below-normal priority)")
    t0 = time.time()
    results = []
    done = 0
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
        futs = [ex.submit(_worker, t) for t in tasks]
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if progress and (done % max(1, len(tasks) // 20) == 0 or done == len(tasks)):
                el = time.time() - t0
                nf = sum(1 for r in results if r["fired"])
                print(f"[sweep] {done}/{len(tasks)}  fired={nf}  "
                      f"elapsed={el:.0f}s  eta={el/done*(len(tasks)-done):.0f}s",
                      flush=True)

    # ---- aggregate per cell ----
    agg = {}
    for r in results:
        key = json.dumps(r["cell"], sort_keys=True)
        agg.setdefault(key, {"cell": r["cell"], "seeds": []})
        agg[key]["seeds"].append({
            "seed": r["seed"], "real": r["real"], "control": r["control"],
            "fired": r["fired"], "reasons": r["reasons"], "near_watch": r["near_watch"],
        })
    cell_table = []
    for key, v in agg.items():
        nf = sum(1 for s in v["seeds"] if s["fired"])
        cell_table.append({
            "cell": v["cell"],
            "n_seeds": len(v["seeds"]),
            "n_fired": nf,
            "fire_fraction": nf / len(v["seeds"]),
            "seeds": v["seeds"],
        })

    total = len(results)
    total_fired = sum(1 for r in results if r["fired"])
    any_reliable_cell = any(c["fire_fraction"] >= 0.6 for c in cell_table)
    if total_fired == 0:
        verdict = "UNRESOLVED"
        statement = (f"Across {len(cell_table)} parameter regimes and {seeds} seeds "
                     f"each ({total} runs, {epochs} epochs), no run beat its "
                     f"scrambled control. No replicator emerged in the swept "
                     f"budget — cold, honestly.")
    elif any_reliable_cell:
        verdict = "FEATURE"
        statement = (f"Emergence fired reliably (>=60% of seeds) in at least one "
                     f"parameter regime — order is a feature of the substrate "
                     f"there, reproduced across seeds vs the scrambled control.")
    else:
        verdict = "BUG"
        statement = (f"Emergence fired in {total_fired}/{total} runs but never "
                     f"reliably within a single regime — rare / knife-edge, not a "
                     f"robust feature.")

    # ---- headline run for the frontend: the most-ordered real run ----
    def order_score(r):
        # lower final entropy + higher top_share = more order crawled out
        return (r["real"]["max_top_share"], -r["real"]["final_entropy"])
    headline = max(results, key=order_score) if results else None

    payload = {
        "grid": grid,
        "seeds": seeds,
        "epochs": epochs,
        "checkpoint_every": checkpoint_every,
        "elapsed_sec": round(time.time() - t0, 1),
        "total_runs": total,
        "total_fired": total_fired,
        "verdict": {"verdict": verdict, "statement": statement},
        "cell_table": cell_table,
        "headline": headline,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[sweep] done in {payload['elapsed_sec']}s -> {out}")
    print(f"[sweep] verdict: {verdict} — {statement}")
    return payload


def main(argv=None):
    ap = argparse.ArgumentParser(description="the-pot broad soup parameter sweep")
    ap.add_argument("--epochs", type=int, default=50000)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--checkpoint-every", type=int, default=500)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", default="sweep_results.json")
    ap.add_argument("--fast", action="store_true",
                    help="tiny grid+epochs for a smoke run")
    args = ap.parse_args(argv)
    grid = None
    if args.fast:
        grid = {"tape_len": [64], "max_steps": [256, 512],
                "mut_per_tape": [1.0], "soup_size": [256]}
    run_sweep(grid=grid, seeds=args.seeds, epochs=args.epochs,
              checkpoint_every=args.checkpoint_every, workers=args.workers,
              out=args.out)


if __name__ == "__main__":
    main()
