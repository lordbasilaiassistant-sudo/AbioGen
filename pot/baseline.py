"""pot.baseline — the closed baseline (Engine 2): honesty control + extinction anchor.

Unlike the open-ended soup, this engine has a *known* optimum, so it is not a
frontier — it is a sanity check. Agents carry a lookup-table policy
(``policy[cue] -> action``) and try to exploit a hidden ``cue -> correct
action`` mapping. There is **no lifetime learning**: an agent's policy is fixed
at birth, and the only adaptation is evolutionary (selection + mutation across
generations).

The two worlds are byte-for-byte the same harness except for one line — how the
"correct" action for a presentation is produced:

* **STRUCTURED**: ``correct = hidden_map[cue]`` — a stable, learnable regularity.
* **NULL**: ``correct = random action`` — no regularity exists to be learned.

Expected, and re-verified by every run:

* STRUCTURED → most seeds adapt, the majority of the hidden map is recovered,
  capture (mean reward) climbs far above chance.
* NULL → **every seed goes extinct.** Nothing is learnable, so no genome can
  clear the viability floor, and the population empties.

This is the extinction anchor: if a *structureless* world ever sustains life,
the harness is leaking structure and the whole run is VOID (see
``pot.experiment``). The viability floor uses enough presentations that per-agent
reward is tightly concentrated, so a null world's extinction is not a lucky
accident — it is forced.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class BaselineConfig:
    n_cues: int = 16
    n_actions: int = 4
    presentations: int = 256      # T; large so reward is concentrated -> clean null death
    pop: int = 200
    generations: int = 60
    mut_rate: float = 0.08        # per-cue chance an offspring re-rolls its action
    floor_fraction: float = 0.375  # viability floor as a fraction of T (chance=1/n_actions)
    seed: int = 0


@dataclass
class BaselineRun:
    config: dict
    structured: bool
    chance: float
    extinct: bool
    extinct_gen: int              # -1 if never extinct
    trajectory: list              # per-gen dicts
    final_capture: float          # mean reward fraction at the last living gen
    final_best: float
    map_recovered: float          # fraction of hidden map matched by the consensus policy


def run_baseline(config: BaselineConfig, structured: bool) -> BaselineRun:
    """Evolve a population in the structured or null world. Deterministic in seed."""
    rng = np.random.default_rng(config.seed + (0 if structured else 10_000))
    C, A, T, N = config.n_cues, config.n_actions, config.presentations, config.pop
    chance = 1.0 / A
    floor = config.floor_fraction * T

    hidden = rng.integers(0, A, size=C)                 # the learnable regularity
    policy = rng.integers(0, A, size=(N, C))            # random initial genomes

    traj = []
    extinct = False
    extinct_gen = -1
    final_capture = 0.0
    final_best = 0.0
    map_recovered = 0.0

    for gen in range(config.generations):
        # One shared environment sample per generation (identical for both worlds).
        cues = rng.integers(0, C, size=T)
        if structured:
            correct = hidden[cues]
        else:
            correct = rng.integers(0, A, size=T)        # the ONLY difference

        # food[agent] = number of presentations the agent's policy got right.
        chosen = policy[:, cues]                        # (N, T)
        food = np.count_nonzero(chosen == correct[None, :], axis=1)  # (N,)

        # consensus (dominant) policy across the living population
        consensus = np.array(
            [np.bincount(policy[:, c], minlength=A).argmax() for c in range(C)]
        )
        recovered = float(np.count_nonzero(consensus == hidden)) / C

        capture = float(food.mean()) / T
        best = float(food.max()) / T
        traj.append({
            "gen": gen,
            "alive": int(policy.shape[0]),
            "capture": capture,
            "best": best,
            "map_recovered": recovered,
        })
        final_capture, final_best, map_recovered = capture, best, recovered

        # viability: only agents clearing the floor may reproduce
        survivors = np.nonzero(food >= floor)[0]
        if survivors.size == 0:
            extinct = True
            extinct_gen = gen
            traj[-1]["alive"] = 0
            break

        # fitness-weighted refill to N with per-cue mutation
        w = food[survivors].astype(np.float64)
        w = w / w.sum()
        parents = survivors[rng.choice(survivors.size, size=N, p=w)]
        child = policy[parents].copy()
        mut = rng.random((N, C)) < config.mut_rate
        k = int(mut.sum())
        if k:
            child[mut] = rng.integers(0, A, size=k)
        policy = child

    return BaselineRun(
        config=asdict(config),
        structured=structured,
        chance=chance,
        extinct=extinct,
        extinct_gen=extinct_gen,
        trajectory=traj,
        final_capture=final_capture,
        final_best=final_best,
        map_recovered=map_recovered,
    )
