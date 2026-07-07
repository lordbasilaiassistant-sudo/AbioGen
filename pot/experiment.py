"""pot.experiment — multi-seed sweeps, the scrambled control, and the verdict.

This is where the honesty controls become load-bearing. For the open-ended
soup, *every* real run is paired with an identical **scrambled control** run
(same seed, same parameters, structure destroyed each epoch). An emergence
metric only counts as "fired" when the real run beats its own scrambled control
by a margin — the control subtraction is baked into the firing test, so a metric
that merely has a high noise floor can never masquerade as emergence.

For the closed baseline, every null seed must go extinct and must not beat
chance. If a structureless world sustains life or beats chance, the run is
**VOID** — a signal that the harness is leaking structure.

The three verdicts are earned from thresholds on the measured numbers, never
hardcoded:

* **FEATURE**  — emergence fires reliably across seeds (and, in a sweep, across
  parameter regimes).
* **BUG**      — it fires only rarely / under knife-edge tuning.
* **UNRESOLVED** — no emergence separates from the control within the swept
  budget (the honest "cold" result), or it swings on arbitrary parameters.

Run:  ``python -m pot.experiment --quick``  (or ``--full``, or defaults).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict

from .soup import SoupConfig, run_soup, summarize
from .baseline import BaselineConfig, run_baseline
from . import ledger, HAVE_RUST

# ---- firing thresholds (margins are *over the scrambled control*) -----------
REPL_MARGIN = 0.02      # real repl_rate must beat control by this
NEAR_MARGIN = 0.15      # near_repl noise floor is high; demand a real gap
SHARE_MARGIN = 0.10     # a lineage sweep: top_share real >> control
UNIQ_MARGIN = 0.10      # ... with diversity crashing in real but not control
# motif_share is confounded by benign copy-autocorrelation (measured: real is
# ~2x control, gap <= ~0.015 in cold runs with zero replication). So it may fire
# ONLY far above that noise floor: a real quasispecies replicator repeats its
# genome across many tapes and pushes one k-mer's share to 0.1-0.5+.
MOTIF_MARGIN = 0.10     # real must beat control by 6x the measured noise gap
MOTIF_FLOOR = 0.12      # ...and clear an absolute bar benign autocorrelation can't

# ---- verdict thresholds -----------------------------------------------------
FEATURE_FRAC = 0.60     # fires in >= 60% of seeds -> reliable
CHANCE_MARGIN = 0.03    # null capture may not exceed chance by more than this


def _fires(real: dict, ctrl: dict) -> tuple:
    """Did emergence fire on this real run, judged against its scrambled control?

    Only two signals are allowed to *fire* the verdict, because only these two
    are things a scrambled control genuinely nulls out AND that mean "a
    replicator specifically":

      * ``repl_rate`` — the fraction of interactions where a tape copied its
        *own original content* over its partner. Noise floor ~0; in a scrambled
        world genomes are destroyed every epoch so this cannot build up.
      * a **lineage sweep** — ``top_share`` rising while ``unique_ratio`` crashes:
        identical tapes proliferating. A shuffled control cannot accumulate
        identical tapes.

    ``near_repl`` is deliberately **excluded** from firing. It is a genuine
    early-warning line to watch, but real dynamics create internal correlation
    even with zero replication, so ``near_repl > scrambled-control`` is
    confounded — an elevated near_repl is reported (see ``_near_watch``) but can
    never, by itself, be called emergence.

    Returns (fired: bool, reasons: list[str]) so the ledger can say *why*.
    """
    reasons = []
    if real["peak_repl_rate"] - ctrl["peak_repl_rate"] > REPL_MARGIN:
        reasons.append("repl_rate>control")
    lineage_sweep = (
        (real["max_top_share"] - ctrl["max_top_share"] > SHARE_MARGIN)
        and (ctrl["min_unique_ratio"] - real["min_unique_ratio"] > UNIQ_MARGIN)
    )
    if lineage_sweep:
        reasons.append("lineage_sweep>control")
    # motif takeover: a dominant k-mer, far above the confounded noise floor
    rm = real.get("peak_motif_share", 0.0)
    if (rm - ctrl.get("peak_motif_share", 0.0) > MOTIF_MARGIN) and (rm > MOTIF_FLOOR):
        reasons.append("motif_takeover>control")
    return (len(reasons) > 0, reasons)


def _near_watch(real: dict, ctrl: dict) -> bool:
    """A *non-firing* early-warning flag: near_repl elevated over control.

    Reported for the human to watch, never counted as emergence — near_repl is
    confounded by benign autocorrelation the scrambled control destroys.
    """
    return real["peak_near_repl"] - ctrl["peak_near_repl"] > NEAR_MARGIN


def run_soup_experiment(base: SoupConfig, seeds, outdir=None, progress=False):
    """Run real + scrambled control for each seed; return per-seed records."""
    records = []
    for s in seeds:
        real_cfg = SoupConfig(**{**asdict(base), "seed": s, "scramble": False})
        ctrl_cfg = SoupConfig(**{**asdict(base), "seed": s, "scramble": True})
        cp = os.path.join(outdir, f"soup_seed{s}.json") if outdir else None
        if progress:
            print(f"[soup] seed {s} real ...", flush=True)
        real = run_soup(real_cfg, checkpoint_path=cp, progress=progress)
        if progress:
            print(f"[soup] seed {s} scrambled control ...", flush=True)
        ctrl = run_soup(ctrl_cfg)
        rs, ks = summarize(real), summarize(ctrl)
        fired, reasons = _fires(rs, ks)
        records.append({
            "seed": s,
            "real": rs,
            "control": ks,
            "fired": fired,
            "reasons": reasons,
            "near_watch": _near_watch(rs, ks),
            "real_trajectory": real.trajectory,
            "control_trajectory": ctrl.trajectory,
            "dominant": real.dominant,
        })
    return records


def soup_verdict(records) -> dict:
    """Feature / bug / unresolved, from the fraction of seeds that fired."""
    n = len(records)
    n_fire = sum(1 for r in records if r["fired"])
    frac = n_fire / n if n else 0.0
    if n_fire == 0:
        verdict = "UNRESOLVED"
        statement = ("No emergence separated from the scrambled control in any "
                     "seed within the swept budget. Cold, honestly.")
        confidence = "low-to-moderate (bounded by compute, not by evidence of absence)"
    elif frac >= FEATURE_FRAC:
        verdict = "FEATURE"
        statement = (f"A self-replicator emerged and beat the scrambled control "
                     f"in {n_fire}/{n} seeds — reliable, not a fluke.")
        confidence = "moderate-to-high (reproduced across seeds vs control)"
    else:
        verdict = "BUG"
        statement = (f"Emergence fired in only {n_fire}/{n} seeds — rare / "
                     f"knife-edge, not a robust feature of the substrate.")
        confidence = "moderate"
    return {
        "verdict": verdict, "statement": statement, "confidence": confidence,
        "seeds": n, "seeds_fired": n_fire, "fire_fraction": frac,
    }


def run_two_arm_experiment(base: SoupConfig, seeds, outdir=None):
    """WILD vs TENDED, each against its own scrambled control.

    The comparative question your two-arm design asks: does order need a tender,
    or does it arise on its own? Both arms start identically; TENDED adds the
    data-gated nurture operator. Each arm is judged against its OWN scrambled
    control, so TENDED's order only counts if it survives structure destruction
    (i.e. it is not the nurture operator mechanically manufacturing uniformity).

    The verdict is earned from the measured numbers:
      * NURTURE_NECESSARY  — WILD cold, TENDED real (beats its scramble)
      * NURTURE_ACCELERATES — both arms show real order
      * COLD               — neither arm separates from its control
      * NURTURE_ARTIFACT   — TENDED "order" matches its own scramble (lala-land)
    """
    arms = {"wild": [], "tended": []}
    for s in seeds:
        common = {**asdict(base), "seed": s}
        for arm, nurture in (("wild", False), ("tended", True)):
            real = run_soup(SoupConfig(**{**common, "nurture": nurture,
                                          "scramble": False}))
            ctrl = run_soup(SoupConfig(**{**common, "nurture": nurture,
                                          "scramble": True}))
            rs, ks = summarize(real), summarize(ctrl)
            fired, reasons = _fires(rs, ks)
            arms[arm].append({
                "seed": s, "real": rs, "control": ks, "fired": fired,
                "reasons": reasons, "trajectory": real.trajectory,
                "control_trajectory": ctrl.trajectory, "dominant": real.dominant,
            })

    def frac(a):
        return sum(1 for r in arms[a] if r["fired"]) / len(arms[a]) if arms[a] else 0.0
    wild_f, tended_f = frac("wild"), frac("tended")
    # did TENDED's apparent order merely echo its own scramble? (lala-land check)
    tended_artifact = any(
        (r["real"]["peak_motif_share"] - r["control"]["peak_motif_share"]) <= MOTIF_MARGIN
        and r["real"]["max_top_share"] > 0.02  # apparent order, but not control-beating
        for r in arms["tended"]
    ) and tended_f == 0.0

    if wild_f > 0 and tended_f > 0:
        verdict, statement = "NURTURE_ACCELERATES", (
            f"Real order in BOTH arms (wild {wild_f:.0%}, tended {tended_f:.0%} of "
            f"seeds) — the substrate produces order on its own; nurture accelerates it.")
    elif tended_f > 0 and wild_f == 0:
        verdict, statement = "NURTURE_NECESSARY", (
            f"WILD stayed cold; TENDED produced control-surviving order in "
            f"{tended_f:.0%} of seeds. In this budget order needed the tender "
            f"(provisional — WILD is compute-bound).")
    elif tended_artifact:
        verdict, statement = "NURTURE_ARTIFACT", (
            "TENDED showed apparent order that did NOT survive its own scrambled "
            "control — the nurture was compounding noise. Discarded as lala-land.")
    else:
        verdict, statement = "COLD", (
            "Neither arm separated from its scrambled control within the budget.")

    payload = {
        "verdict": verdict, "statement": statement,
        "wild_fire_fraction": wild_f, "tended_fire_fraction": tended_f,
        "arms": arms,
    }
    if outdir:
        with open(os.path.join(outdir, "two_arm.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    return payload


def run_baseline_experiment(base: BaselineConfig, seeds):
    """Structured vs null across seeds; the extinction anchor + VOID check."""
    struct, null = [], []
    for s in seeds:
        cfg = BaselineConfig(**{**asdict(base), "seed": s})
        struct.append(run_baseline(cfg, structured=True))
        null.append(run_baseline(cfg, structured=False))
    chance = null[0].chance if null else 1.0
    null_all_extinct = all(r.extinct for r in null)
    null_beats_chance = any(r.final_capture > chance + CHANCE_MARGIN for r in null)
    void = (not null_all_extinct) or null_beats_chance

    struct_adapted = sum(
        1 for r in struct if (not r.extinct and r.final_capture > chance + CHANCE_MARGIN)
    )
    struct_map = sum(r.map_recovered for r in struct) / len(struct) if struct else 0.0

    if void:
        verdict = "VOID"
        statement = ("A structureless (null) world sustained life or beat chance "
                     "— the harness is leaking structure; this run is void.")
    else:
        verdict = "ANCHORED"
        statement = (f"Null world went extinct every seed ({len(null)}/{len(null)}); "
                     f"structured world adapted in {struct_adapted}/{len(struct)} "
                     f"seeds, recovering {struct_map:.0%} of the hidden map on "
                     f"average. Extinction anchor holds.")
    return {
        "verdict": verdict,
        "statement": statement,
        "chance": chance,
        "null_all_extinct": null_all_extinct,
        "null_beats_chance": null_beats_chance,
        "struct_adapted": struct_adapted,
        "struct_map_recovered_mean": struct_map,
        "structured": [
            {"seed": r.config["seed"], "capture": r.final_capture,
             "map_recovered": r.map_recovered, "extinct": r.extinct,
             "trajectory": r.trajectory}
            for r in struct
        ],
        "null": [
            {"seed": r.config["seed"], "capture": r.final_capture,
             "extinct": r.extinct, "extinct_gen": r.extinct_gen,
             "trajectory": r.trajectory}
            for r in null
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="the-pot experiment + verdict harness")
    ap.add_argument("--quick", action="store_true",
                    help="tiny run for CI / smoke (fast, low evidence)")
    ap.add_argument("--full", action="store_true",
                    help="longer multi-seed sweep (uses more cores/time)")
    ap.add_argument("--seeds", type=int, default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--results", default="results.json")
    ap.add_argument("--ledger", default="ledger.json")
    ap.add_argument("--progress", action="store_true")
    args = ap.parse_args(argv)

    from .util import set_low_priority
    set_low_priority()  # be polite on a machine that is also being used

    if args.quick:
        n_seeds = args.seeds or 2
        soup_base = SoupConfig(soup_size=128, tape_len=64, max_steps=256,
                               epochs=args.epochs or 200, checkpoint_every=50)
        base_bl = BaselineConfig(generations=40)
    elif args.full:
        n_seeds = args.seeds or 8
        soup_base = SoupConfig(soup_size=512, tape_len=64, max_steps=512,
                               epochs=args.epochs or 20000, checkpoint_every=200)
        base_bl = BaselineConfig(generations=80)
    else:
        n_seeds = args.seeds or 4
        soup_base = SoupConfig(soup_size=256, tape_len=64, max_steps=384,
                               epochs=args.epochs or 3000, checkpoint_every=100)
        base_bl = BaselineConfig(generations=60)

    seeds = list(range(n_seeds))
    os.makedirs(args.outdir, exist_ok=True)

    # ---- predict BEFORE running -------------------------------------------
    entry = ledger.new_entry(
        name=f"soup+baseline ({'quick' if args.quick else 'full' if args.full else 'default'}), "
             f"{n_seeds} seeds, {soup_base.epochs} epochs",
        prediction={
            "soup_verdict": "UNRESOLVED",
            "soup_reason": "No replicator has emerged in ~11k prior epochs; this "
                           "budget is unlikely to cross over, so expect no "
                           "separation from the scrambled control.",
            "baseline_verdict": "ANCHORED",
            "baseline_reason": "Null must go extinct every seed; structured must "
                               "beat chance and recover most of the hidden map.",
        },
        rationale="Predict-before-run: state the expectation, then let the data "
                  "confirm or refute it.",
    )

    print(f"[experiment] rust={HAVE_RUST}  seeds={seeds}  soup_epochs={soup_base.epochs}")
    print("[experiment] running soup (real + scrambled control per seed) ...")
    soup_records = run_soup_experiment(soup_base, seeds, outdir=args.outdir,
                                       progress=args.progress)
    sv = soup_verdict(soup_records)
    print(f"[experiment] soup verdict: {sv['verdict']} — {sv['statement']}")

    print("[experiment] running closed baseline (structured vs null) ...")
    bl = run_baseline_experiment(base_bl, seeds)
    print(f"[experiment] baseline verdict: {bl['verdict']} — {bl['statement']}")

    results = {
        "have_rust": HAVE_RUST,
        "n_seeds": n_seeds,
        "soup_config": asdict(soup_base),
        "baseline_config": asdict(base_bl),
        "soup": {"verdict": sv, "records": soup_records},
        "baseline": bl,
    }
    with open(os.path.join(args.outdir, args.results), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # ---- record actual vs predicted ---------------------------------------
    checks = [
        ("soup_verdict", entry["prediction"]["soup_verdict"], sv["verdict"],
         entry["prediction"]["soup_verdict"] == sv["verdict"]),
        ("baseline_verdict", entry["prediction"]["baseline_verdict"], bl["verdict"],
         entry["prediction"]["baseline_verdict"] == bl["verdict"]),
    ]
    overall = "confirmed" if all(c[3] for c in checks) else "refuted-in-part"
    entry = ledger.finalize(
        entry,
        actual={"soup_verdict": sv["verdict"], "baseline_verdict": bl["verdict"],
                "soup_seeds_fired": sv["seeds_fired"]},
        verdict=overall,
        checks=checks,
    )
    ledger.append(os.path.join(args.outdir, args.ledger), entry)

    print(f"[experiment] wrote {args.results} and appended to {args.ledger} "
          f"(prediction {overall}).")
    return results


if __name__ == "__main__":
    main()
