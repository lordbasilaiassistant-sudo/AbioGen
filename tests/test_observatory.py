"""The observatory must score rungs, catch anomalies the rungs miss, and stay
silent when real and control agree — all as pure observation."""

from pot.observatory import (
    observe, phase_transitions, control_envelope_anomalies, rung_scoreboard,
)


def _traj(motif_series, top=0.004, uniq=1.0, entropy=3.5, repl=0.0):
    return [{"epoch": i * 100, "repl_rate": repl, "unique_ratio": uniq,
             "top_share": top, "entropy": entropy, "near_repl_max": 0.3,
             "near_repl_mean": 0.1, "motif_share": m}
            for i, m in enumerate(motif_series)]


def test_flat_real_vs_control_is_silent():
    flat = _traj([0.01] * 8)
    rep = observe(flat, flat, {"peak_motif_share": 0.01, "peak_repl_rate": 0.0,
                               "min_unique_ratio": 1.0},
                  {"peak_motif_share": 0.01, "peak_repl_rate": 0.0,
                   "min_unique_ratio": 1.0})
    assert rep["surprise_index"] == 0.0
    assert rep["anomalies"] == []
    assert all(not r["reached"] for r in rep["rungs"])


def test_motif_takeover_is_flagged_as_anomaly_and_rung():
    real = _traj([0.01, 0.02, 0.05, 0.15, 0.30, 0.35], uniq=0.6, entropy=2.0)
    ctrl = _traj([0.01] * 6)
    rsum = {"peak_motif_share": 0.35, "peak_repl_rate": 0.0, "min_unique_ratio": 0.6}
    csum = {"peak_motif_share": 0.01, "peak_repl_rate": 0.0, "min_unique_ratio": 0.99}
    rep = observe(real, ctrl, rsum, csum)
    assert rep["surprise_index"] > 0.1
    metrics = {a["metric"] for a in rep["anomalies"]}
    assert "motif_share" in metrics
    assert any(r["reached"] and r["rung"] == 0.5 for r in rep["rungs"])


def test_phase_transition_detects_a_sudden_jump():
    # a metric that snaps on partway through must register a change-point
    real = _traj([0.01, 0.01, 0.01, 0.40, 0.41, 0.42])
    events = phase_transitions(real, keys=["motif_share"])
    assert events
    assert events[0]["metric"] == "motif_share"
    assert events[0]["to"] > events[0]["from"]


def test_anomaly_scan_is_channel_agnostic():
    # an entropy collapse with no motif change must still be caught (a channel no
    # single rung is keyed on) — the byproduct catcher.
    real = _traj([0.01] * 6, entropy=1.5)
    ctrl = _traj([0.01] * 6, entropy=3.5)
    anomalies = control_envelope_anomalies(real, ctrl)
    assert any(a["metric"] == "entropy" for a in anomalies)
