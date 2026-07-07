"""pot.hunt — the search for an emergent, *isolable* self-replicator.

The goal is to *find* one, not to claim we have. This tool runs the regime the
literature points at (arXiv:2406.19108: BFF soups birth self-replicators with no
fitness, best at low/zero mutation), captures the actual tapes caught copying
themselves, and then does the thing a mere signal can't: **re-runs each captured
tape in the bare interpreter against fresh partners.** A replication *signal*
(repl_rate beating the scrambled control) says copying happened in the soup; an
*isolated* replicator that copies itself onto naive partners in the empty
interpreter is the real, standalone finding.

Honesty stance travels with the hunt:
  * every run is judged against its own scrambled control (real vs artifact),
  * a captured tape only counts as a replicator if it reproduces in isolation,
  * "self-replication" is the claim — never "intelligence".

Run:  python -m pot.hunt --epochs 16000 --seeds 8
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

# The regime the literature says is hottest for BFF emergence: low/zero mutation,
# a generous step budget so programs can actually run a copy loop.
DEFAULT_MUTATIONS = [0.0, 0.05, 0.25]
DEFAULT_STEPS = [1024, 2048]


def _init_worker():
    from .util import set_low_priority
    set_low_priority()


def verify_in_isolation(genome_hex: str, partner_hex: str, max_steps: int,
                        n_trials: int = 300, seed: int = 12345) -> dict:
    """Re-run a captured tape in the bare interpreter. Does it copy itself?"""
    from .bff import run_tape, INSTRUCTION_SET
    g = bytes.fromhex(genome_hex)
    L = len(g)
    inst = np.frombuffer(INSTRUCTION_SET, np.uint8)
    rng = np.random.default_rng(seed)

    def copies_onto(partner: bytes) -> bool:
        t = bytearray(g + partner)
        run_tape(t, max_steps)
        if bytes(t[L:]) == g:            # partner (2nd half) became the genome
            return True
        t = bytearray(partner + g)
        run_tape(t, max_steps)
        return bytes(t[:L]) == g          # genome imposed itself from the 2nd slot

    # 1) the exact partner it was caught with (sanity: should reproduce)
    exact = copies_onto(bytes.fromhex(partner_hex)) if partner_hex else False
    # 2) fresh partners drawn from the instruction set (naive programs)
    inst_hits = sum(copies_onto(bytes(rng.choice(inst, size=L)))
                    for _ in range(n_trials))
    # 3) fresh partners drawn from the full byte range (pure noise)
    full_hits = sum(copies_onto(bytes(rng.integers(0, 256, size=L)))
                    for _ in range(n_trials))
    return {
        "reproduced_exact_partner": exact,
        "isolation_rate_instr": inst_hits / n_trials,
        "isolation_rate_fullbyte": full_hits / n_trials,
        "n_trials": n_trials,
    }


def _worker(task):
    from .soup import SoupConfig, run_soup, summarize
    from .experiment import _fires
    mut, steps, seed, epochs, soup_size = task
    common = dict(soup_size=soup_size, tape_len=64, max_steps=steps,
                  mut_per_tape=mut, epochs=epochs, checkpoint_every=500, seed=seed)
    real = run_soup(SoupConfig(capture_events=40, **common))
    ctrl = run_soup(SoupConfig(scramble=True, **common))
    rs, ks = summarize(real), summarize(ctrl)
    fired, reasons = _fires(rs, ks)

    verified = []
    if fired and real.replicators:
        # de-dup captured genomes, verify the distinct ones in isolation
        seen = set()
        for rep in real.replicators:
            if rep["genome"] in seen:
                continue
            seen.add(rep["genome"])
            v = verify_in_isolation(rep["genome"], rep["partner"], steps)
            verified.append({**rep, **v})
            if len(verified) >= 8:
                break

    return {
        "mut": mut, "steps": steps, "seed": seed,
        "peak_repl_rate": rs["peak_repl_rate"],
        "control_repl_rate": ks["peak_repl_rate"],
        "fired": fired, "reasons": reasons,
        "n_captured": len(real.replicators),
        "verified": verified,
    }


def run_hunt(mutations=None, steps_list=None, seeds=8, epochs=16000, workers=None,
             soup_size=512, out="research/hunt_results.json"):
    from .util import set_low_priority, polite_worker_count
    os.environ["RAYON_NUM_THREADS"] = "1"
    set_low_priority()
    mutations = mutations or DEFAULT_MUTATIONS
    steps_list = steps_list or DEFAULT_STEPS
    workers = workers or polite_worker_count()
    tasks = [(m, s, sd, epochs, soup_size)
             for m in mutations for s in steps_list for sd in range(seeds)]
    print(f"[hunt] {len(tasks)} runs (+ controls), {epochs} epochs, soup={soup_size}, "
          f"mut={mutations} steps={steps_list} seeds={seeds}, {workers} polite workers")

    t0 = time.time()
    results, done = [], 0
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
        for fut in as_completed([ex.submit(_worker, t) for t in tasks]):
            results.append(fut.result())
            done += 1
            if done % max(1, len(tasks) // 15) == 0 or done == len(tasks):
                nf = sum(1 for r in results if r["fired"])
                nv = sum(1 for r in results for v in r["verified"]
                         if v["isolation_rate_instr"] > 0 or v["isolation_rate_fullbyte"] > 0)
                el = time.time() - t0
                print(f"[hunt] {done}/{len(tasks)}  fired={nf}  isolated_replicators={nv}  "
                      f"elapsed={el:.0f}s", flush=True)

    # ---- aggregate ----
    n = len(results)
    fired = [r for r in results if r["fired"]]
    # an isolated replicator: reproduces onto fresh naive partners above chance
    isolated = []
    for r in results:
        for v in r["verified"]:
            if v["isolation_rate_instr"] >= 0.05 or v["isolation_rate_fullbyte"] >= 0.05:
                isolated.append({"mut": r["mut"], "steps": r["steps"],
                                 "seed": r["seed"], **v})
    isolated.sort(key=lambda v: -max(v["isolation_rate_instr"], v["isolation_rate_fullbyte"]))

    # emergence rate per regime, to compare against the literature's ~40%
    by_regime = {}
    for r in results:
        key = f"mut={r['mut']}_steps={r['steps']}"
        by_regime.setdefault(key, {"n": 0, "fired": 0})
        by_regime[key]["n"] += 1
        by_regime[key]["fired"] += int(r["fired"])
    for k in by_regime:
        by_regime[k]["fire_rate"] = by_regime[k]["fired"] / by_regime[k]["n"]

    payload = {
        "reference": "arXiv:2406.19108 (Computational Life; BFF soups, ~40% "
                     "emergence in 16k epochs, no fitness)",
        "epochs": epochs, "seeds": seeds,
        "total_runs": n,
        "runs_fired": len(fired),
        "emergence_rate_overall": len(fired) / n if n else 0.0,
        "emergence_rate_by_regime": by_regime,
        "isolated_replicators": isolated,
        "n_isolated": len(isolated),
        "elapsed_sec": round(time.time() - t0, 1),
        "runs": results,
    }
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[hunt] done in {payload['elapsed_sec']}s -> {out}")
    print(f"[hunt] emergence: {len(fired)}/{n} runs fired; "
          f"{len(isolated)} isolable self-replicators verified in the bare interpreter")
    if isolated:
        best = isolated[0]
        print(f"[hunt] best isolated replicator: mut={best['mut']} steps={best['steps']} "
              f"seed={best['seed']} isolation_rate(instr)={best['isolation_rate_instr']:.2%} "
              f"(fullbyte)={best['isolation_rate_fullbyte']:.2%}")
    return payload


def main(argv=None):
    ap = argparse.ArgumentParser(description="hunt for an isolable emergent replicator")
    ap.add_argument("--epochs", type=int, default=16000)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--soup-size", type=int, default=512,
                    help="bigger soup nucleates replicators far more often")
    ap.add_argument("--mutations", type=float, nargs="+", default=None)
    ap.add_argument("--steps", type=int, nargs="+", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", default="research/hunt_results.json")
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args(argv)
    if args.fast:
        run_hunt(mutations=[0.0, 0.25], steps_list=[1024], seeds=args.seeds,
                 epochs=args.epochs, workers=args.workers,
                 soup_size=args.soup_size, out=args.out)
    else:
        run_hunt(mutations=args.mutations, steps_list=args.steps, seeds=args.seeds,
                 epochs=args.epochs, workers=args.workers,
                 soup_size=args.soup_size, out=args.out)


if __name__ == "__main__":
    main()
