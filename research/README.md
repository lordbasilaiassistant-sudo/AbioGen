# research/ — the durable record of the hunt

This folder is the lab notebook. It holds real run artifacts (with provenance),
the honest state of what we have and have not shown, and the roadmap. Future
experiments read `runs/*/manifest.json` to know exactly what produced each
result and how to reproduce it.

**The goal is to *find* emergent order, not to claim we have.** Every number
here is earned from a real run and judged against a scrambled control. Nothing
is asserted.

---

## The honest state of findings (updated as runs land)

| rung | claim | status |
|---|---|---|
| 0 | **self-replication** — copying arises from noise, no fitness | **real but contextual.** `pot.hunt` (48 runs, fixed RNG): copying events are real and control-gated (captured tapes reproduce with their exact captured partner), but **0% reproduce against fresh naive partners** — no *autonomous* replicator isolated yet. Emergence rate only ~2% (1/48) vs the reference's ~40% — **diagnosed as soup-size limited** (ours 512 tapes vs the paper's ~131k; nucleation is a rare event that scales with soup size). Scaled 8,192-tape hunt running to nucleate + isolate one. |
| 0 | **extinction anchor** — a structureless world dies | **holds** — null goes extinct every seed; structured recovers ~95% of a hidden map. |
| — | **nurture (TENDED arm)** — a life-assisting rule surfaces real order | **real, control-surviving** in ~50% of seeds (dominant motif to 0.37, scramble stays flat). NURTURE_NECESSARY at the hard regime; WILD self-replicates alone at the easy one. |
| 1+ | heredity, open-ended novelty, evolved function, collectives, sociality, adaptation | **not yet built / not shown.** |

**What we have NOT shown, and will not claim:** intelligence, cognition,
emotion, or sociality. Those are many rungs up and, for anything emotion-shaped,
unclimbed by anyone in any artificial soup. Self-replication is life-like; it is
not intelligence.

### Grounding in real science

- **arXiv:2406.19108 — "Computational Life: How Well-formed, Self-replicating
  Programs Emerge from Simple Interaction"** (Agüera y Arcas et al.). On the same
  BFF substrate, self-replicators emerge from random programs with **no fitness
  function**, in **~40% of runs within 16k epochs**, and can arise even with **no
  mutation**. Our `repl_rate` signal at low mutation reproduces this phenomenon;
  our contribution is the honesty apparatus (scrambled control, extinction
  anchor) and the WILD-vs-TENDED comparison, plus isolation testing.
- Adjacent: Avida (evolved logic functions from scratch), Tierra, Fontana's
  AlChemy, Kauffman's autocatalytic sets, Bedau's open-ended-evolution activity
  statistics (the basis for the rung-2 novelty test).

---

## The ladder (the roadmap)

Each rung is a real, measurable, control-gated test. We climb only as far as the
data earns, and we report the rung we can verify plus the gap to the next.

0. **Self-replication** — a tape copies itself through the interpreter.
   *Test:* `repl_rate` and motif-share beat the scrambled control; a captured
   tape reproduces in the bare interpreter against naive partners (`pot.hunt`).
1. **Heredity + variation** — offspring resemble parents above chance, mutations
   accumulate. *Test:* parent/child similarity vs shuffled pairing.
2. **Open-ended novelty** — new adaptive structure keeps appearing, never
   saturating. *Test:* Bedau activity statistics vs the scrambled control.
3. **Evolved function** — tapes compute non-trivial input→output maps.
   *Test:* mutual information between an injected input region and output, vs
   control.
4. **Collectives** — groups persist and reproduce as units (a major transition).
5. **Communication / sociality** — behaviour adaptively depends on a shared
   channel. *Test:* channel-ablation changes fitness/behaviour.
   - **The open line** (issue #14): the shared channel doubles as a golden-record
     gesture — a medium the beings could one day use to reach *us*. We seed
     nothing in it, reward nothing, and keep a dormant listening post that flags
     only control-surviving structure (a code, a language they made). Present,
     never shoved in their faces; discovered, not trained. Listen, don't
     broadcast. It cannot tell us whether we are someone's experiment — it is the
     most honest version of the gesture, not a proof.
6. **Lifetime adaptation** — plasticity within a life, not just across
   generations.

Design principle (from the vision): **add life-assisting *rules*, never
training.** Rules are Earth-like substrate physics — spatiality, metabolism, a
shared channel, longer tapes, inheritance. Tests are *observers*, never fitness
functions. Intelligence, if it comes, is the soup's; our instruments only watch.

Planned substrate rules (opt-in; WILD stays the null): 2D spatial world,
metabolic energy cost per executed step, a readable/writable shared environment
channel, longer tapes.

---

## Folder layout

```
research/
  README.md            this file
  INDEX.md             one row per archived run (auto-appended by pot.archive)
  hunt_results.json    latest emergence hunt (pot.hunt): rates + isolated replicators
  runs/
    <UTCstamp>_<name>/
      manifest.json    provenance: git commit, env, configs, verdicts, reproduce cmds
      *.json           snapshot of the result files at that moment
```

### Artifact schemas (for future readers/parsers)

- **`results.json`** (`pot.experiment`): `soup.verdict`, `soup.records[]`
  (per-seed real/control summaries + trajectories), `baseline` (structured vs
  null, extinction), configs.
- **`sweep_results.json`** (`pot.sweep`): `cell_table[]` (per-regime fire
  fraction), `headline` (fullest trajectory), `verdict`.
- **`two_arm.json`** (`pot.experiment.run_two_arm_experiment`): WILD vs TENDED,
  each vs its own scrambled control; comparative verdict.
- **`hunt_results.json`** (`pot.hunt`): `emergence_rate_by_regime`,
  `isolated_replicators[]` (genomes verified to reproduce in the bare
  interpreter, with isolation rates).
- **`replicator_seed2.json`**: a checkpointed run's trajectory + captured
  genomes.

## Reproduce

```bash
maturin develop --release              # build the fast interpreter
pytest                                 # primitives + honesty controls
python -m pot.experiment --seeds 4 --epochs 4000     # results.json + ledger.json
python -m pot.sweep --epochs 20000 --seeds 4         # sweep_results.json
python -m pot.hunt --epochs 16000 --seeds 8          # research/hunt_results.json
python -m pot.archive --name <label> --note "..."    # snapshot into research/runs/
```

All runs are seeded and deterministic (checkpoint frequency no longer perturbs
the dynamics — the metric sampler has its own RNG). Same seed → same result.
