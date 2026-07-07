"""The honesty controls, as executable invariants.

Two non-negotiables from the design:

  1. The scrambled/structureless control must **not** be able to fire an
     emergence signal — it is the null distribution. We assert it is
     *structurally* incapable of the replicator signature (no exact self-copies
     accumulate, no lineage sweeps), and that the firing gate stays silent.
  2. In the closed baseline, the NULL world must go extinct every seed, and must
     never beat chance. If it did, the harness would be leaking structure and the
     run would be VOID.
"""

import pytest

from pot.soup import SoupConfig, run_soup, summarize
from pot.baseline import BaselineConfig, run_baseline
from pot.experiment import (
    _fires, run_baseline_experiment, run_soup_experiment, soup_verdict,
)


TINY_SOUP = dict(soup_size=64, tape_len=32, max_steps=128,
                 epochs=400, checkpoint_every=100)


# --- control 1: the scrambled soup cannot show the replicator signature -----

def test_scrambled_control_shows_no_replication_signature():
    cfg = SoupConfig(seed=3, scramble=True, **TINY_SOUP)
    s = summarize(run_soup(cfg))
    # A world re-shuffled every epoch cannot accumulate exact self-copies...
    assert s["peak_repl_rate"] == 0.0
    # ...nor a dominant lineage: diversity stays high, top share stays tiny.
    assert s["min_unique_ratio"] > 0.9
    assert s["max_top_share"] < 0.1


def test_scrambled_control_does_not_fire_against_itself():
    # Real-vs-its-own-control on a cold budget must not fire — this is the
    # invariant "if a metric fires on real, the control must not."
    records = run_soup_experiment(
        SoupConfig(**TINY_SOUP), seeds=[0, 1, 2],
    )
    for r in records:
        # the scrambled control side must never present a fireable signature
        ctrl = r["control"]
        assert ctrl["peak_repl_rate"] == 0.0
        assert ctrl["max_top_share"] < 0.1
    # and with no real replicator in this tiny budget, the verdict is honest
    assert soup_verdict(records)["verdict"] in {"UNRESOLVED", "BUG", "FEATURE"}


def test_near_repl_alone_never_fires():
    # near_repl is confounded and must not, by itself, trip the gate. Hand a
    # summary with a huge near_repl gap but zero real replication/sweep signal.
    real = dict(peak_repl_rate=0.0, peak_near_repl=0.99, min_unique_ratio=1.0,
                max_top_share=0.01, min_entropy=3.5, final_entropy=4.0)
    ctrl = dict(peak_repl_rate=0.0, peak_near_repl=0.10, min_unique_ratio=1.0,
                max_top_share=0.01, min_entropy=3.5, final_entropy=4.0)
    fired, reasons = _fires(real, ctrl)
    assert fired is False
    assert reasons == []


def test_motif_moderate_elevation_does_not_fire():
    # The measured confounded case: real motif ~2x control but tiny in absolute
    # terms (benign copy-autocorrelation, zero replication). Must NOT fire.
    real = dict(peak_repl_rate=0.0, peak_near_repl=0.3, min_unique_ratio=1.0,
                max_top_share=0.01, min_entropy=3.5, final_entropy=4.0,
                peak_motif_share=0.03)
    ctrl = dict(peak_repl_rate=0.0, peak_near_repl=0.3, min_unique_ratio=1.0,
                max_top_share=0.01, min_entropy=3.5, final_entropy=4.0,
                peak_motif_share=0.012)
    fired, reasons = _fires(real, ctrl)
    assert fired is False, reasons


def test_motif_takeover_fires():
    # A genuine quasispecies: one k-mer dominates the soup, far above control.
    real = dict(peak_repl_rate=0.0, peak_near_repl=0.5, min_unique_ratio=0.8,
                max_top_share=0.03, min_entropy=2.0, final_entropy=2.0,
                peak_motif_share=0.42)
    ctrl = dict(peak_repl_rate=0.0, peak_near_repl=0.5, min_unique_ratio=0.99,
                max_top_share=0.01, min_entropy=3.5, final_entropy=5.0,
                peak_motif_share=0.012)
    fired, reasons = _fires(real, ctrl)
    assert fired is True
    assert "motif_takeover>control" in reasons


def test_gate_fires_on_a_real_lineage_sweep():
    # Positive control for the gate itself: a genuine sweep in real but not
    # control must fire, so the gate is not simply always-silent.
    real = dict(peak_repl_rate=0.30, peak_near_repl=0.5, min_unique_ratio=0.02,
                max_top_share=0.95, min_entropy=1.0, final_entropy=1.0)
    ctrl = dict(peak_repl_rate=0.0, peak_near_repl=0.5, min_unique_ratio=0.99,
                max_top_share=0.01, min_entropy=3.5, final_entropy=5.0)
    fired, reasons = _fires(real, ctrl)
    assert fired is True
    assert "repl_rate>control" in reasons
    assert "lineage_sweep>control" in reasons


# --- control 2: the extinction anchor ---------------------------------------

# --- determinism: same seed -> identical results (every figure regenerates) ---

def test_soup_is_deterministic_in_seed():
    cfg = dict(soup_size=64, tape_len=32, max_steps=128, epochs=300,
               checkpoint_every=100, seed=7)
    a = summarize(run_soup(SoupConfig(**cfg)))
    b = summarize(run_soup(SoupConfig(**cfg)))
    assert a == b


def test_baseline_is_deterministic_in_seed():
    cfg = BaselineConfig(seed=5, generations=30)
    a = run_baseline(cfg, structured=True)
    b = run_baseline(cfg, structured=True)
    assert a.final_capture == b.final_capture
    assert a.map_recovered == b.map_recovered
    assert [g["capture"] for g in a.trajectory] == [g["capture"] for g in b.trajectory]


FAST_BASE = dict(generations=40, presentations=256, pop=200)


def test_null_world_goes_extinct_every_seed():
    for seed in range(5):
        cfg = BaselineConfig(seed=seed, **FAST_BASE)
        run = run_baseline(cfg, structured=False)
        assert run.extinct, f"null seed {seed} did not go extinct"
        assert run.final_capture <= run.chance + 0.03


def test_structured_world_adapts_and_survives():
    for seed in range(5):
        cfg = BaselineConfig(seed=seed, **FAST_BASE)
        run = run_baseline(cfg, structured=True)
        assert not run.extinct, f"structured seed {seed} went extinct"
        assert run.final_capture > run.chance + 0.03
        assert run.map_recovered >= 0.5


def test_extinction_anchor_verdict_is_anchored_not_void():
    bl = run_baseline_experiment(BaselineConfig(**FAST_BASE), seeds=[0, 1, 2, 3])
    assert bl["verdict"] == "ANCHORED"
    assert bl["null_all_extinct"] is True
    assert bl["null_beats_chance"] is False
    assert bl["struct_adapted"] == 4
