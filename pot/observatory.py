"""pot.observatory — read where the soup stands, and catch what we didn't predict.

Two jobs, both pure *observation* (never selection):

1. **Rung scoreboard.** For each rung of the ladder we can currently measure,
   report whether the real run beats its scrambled control — so any run is
   legible across every rung at once, and we always know where they stand.

2. **The surprise detector.** The interesting emergence in an open-ended system
   is usually in a channel nobody thought to watch. So beyond the named rungs we
   run two channel-agnostic scans on the trajectory:
     * **phase transitions** — sudden change-points in *any* tracked metric (the
       signature of something switching on), and
     * **control-envelope anomalies** — any metric where the real run departs the
       scrambled control's envelope by a margin, ranked into a single per-run
       ``surprise_index`` so runs can be sorted by "how much did this do that the
       structureless null never does."

Nothing here selects or trains. It only measures, always against the control.
"""

from __future__ import annotations

import numpy as np

# every time series the soup checkpoints; the surprise scan watches all of them,
# including ones no rung is defined for (that is the point).
TRACKED = ["repl_rate", "unique_ratio", "top_share", "entropy",
           "near_repl_max", "near_repl_mean", "motif_share"]

# for each metric, the direction that means "more order / more structure"
INTERESTING_DIR = {
    "repl_rate": +1, "unique_ratio": -1, "top_share": +1, "entropy": -1,
    "near_repl_max": +1, "near_repl_mean": +1, "motif_share": +1,
}


def _series(traj, key):
    return np.array([c.get(key, 0.0) for c in traj], dtype=float)


def phase_transitions(traj, keys=None, z=4.0, min_points=6):
    """Change-points: epochs where a metric jumps sharply vs its running baseline.

    A replicator switching on, a lineage sweeping, a byproduct kicking in — all
    show as a step in some series. We flag the largest such steps per metric.
    """
    keys = keys or TRACKED
    events = []
    for key in keys:
        s = _series(traj, key)
        if len(s) < min_points:
            continue
        d = np.abs(np.diff(s))
        if d.size == 0:
            continue
        # Robust baseline: a single big change-point inflates a plain std enough
        # to hide itself, so use the median absolute deviation, which the outlier
        # can't skew.
        med = np.median(d)
        mad = np.median(np.abs(d - med))
        sd = 1.4826 * mad if mad > 0 else 0.0
        # mad==0 (a flat series with lone jumps) falls back to an absolute bar so
        # a steady ramp is never mistaken for a switch-on.
        thresh = z * sd if sd > 0 else 0.10
        for i, jump in enumerate(d):
            if jump > 0.02 and jump > thresh:
                # sd==0 means a flat baseline with a lone jump: report a sentinel
                # rather than dividing by zero.
                sigma = round(float(jump / sd), 1) if sd > 0 else 99.0
                events.append({
                    "metric": key,
                    "epoch": int(traj[i + 1].get("epoch", i + 1)),
                    "from": round(float(s[i]), 4),
                    "to": round(float(s[i + 1]), 4),
                    "jump_sigma": sigma,
                })
    events.sort(key=lambda e: -e["jump_sigma"])
    return events


def control_envelope_anomalies(real_traj, ctrl_traj, keys=None, margin=0.05):
    """Where does the real run leave the scrambled control's envelope?

    Channel-agnostic: any metric whose real excursion exceeds the control's, in
    the order-ward direction, by ``margin`` is an anomaly worth a human's eyes —
    even if no rung is defined for it. This is the byproduct catcher.
    """
    keys = keys or TRACKED
    out = []
    for key in keys:
        r = _series(real_traj, key)
        c = _series(ctrl_traj, key)
        if r.size == 0 or c.size == 0:
            continue
        direction = INTERESTING_DIR.get(key, +1)
        if direction > 0:
            real_x, ctrl_x, gap = r.max(), c.max(), r.max() - c.max()
        else:
            real_x, ctrl_x, gap = r.min(), c.min(), c.min() - r.min()
        if gap > margin:
            out.append({
                "metric": key,
                "real_extreme": round(float(real_x), 4),
                "control_extreme": round(float(ctrl_x), 4),
                "departure": round(float(gap), 4),
            })
    out.sort(key=lambda a: -a["departure"])
    return out


def rung_scoreboard(real_sum, ctrl_sum):
    """Which measurable rungs did this run beat its control on?"""
    def reached(cond):
        return bool(cond)
    board = [
        {"rung": 0, "name": "self-replication (exact copy)",
         "real": round(real_sum.get("peak_repl_rate", 0), 4),
         "control": round(ctrl_sum.get("peak_repl_rate", 0), 4),
         "reached": reached(real_sum.get("peak_repl_rate", 0)
                            - ctrl_sum.get("peak_repl_rate", 0) > 0.02)},
        {"rung": 0.5, "name": "quasispecies motif dominance",
         "real": round(real_sum.get("peak_motif_share", 0), 4),
         "control": round(ctrl_sum.get("peak_motif_share", 0), 4),
         "reached": reached((real_sum.get("peak_motif_share", 0)
                             - ctrl_sum.get("peak_motif_share", 0) > 0.10)
                            and real_sum.get("peak_motif_share", 0) > 0.12)},
        {"rung": 1, "name": "lineage structure (diversity collapse)",
         "real": round(real_sum.get("min_unique_ratio", 1), 4),
         "control": round(ctrl_sum.get("min_unique_ratio", 1), 4),
         "reached": reached(ctrl_sum.get("min_unique_ratio", 1)
                            - real_sum.get("min_unique_ratio", 1) > 0.10)},
    ]
    return board


def observe(real_traj, ctrl_traj, real_sum, ctrl_sum):
    """Full observatory report for one real+control run pair."""
    anomalies = control_envelope_anomalies(real_traj, ctrl_traj)
    surprise = max((a["departure"] for a in anomalies), default=0.0)
    return {
        "rungs": rung_scoreboard(real_sum, ctrl_sum),
        "phase_transitions": phase_transitions(real_traj),
        "anomalies": anomalies,
        "surprise_index": round(float(surprise), 4),
    }
