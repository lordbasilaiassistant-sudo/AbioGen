# AbioGen

*Abiogenesis, generated.* The engine is **AbioGen**; the primordial soup it
runs is the **`pot`** package inside it.

**An accelerated origin-of-intelligence engine.** We build only the substrate
physics. The soup is seeded with pure randomness. There is **no fitness
function, no goal, and no replicator authored by us.** Whatever order emerges
must be something we neither wrote nor can predict.

The question this repo exists to answer — *with real runs, not assertions*:

> Is order/self-replication a **feature** of a well-designed substrate (it
> reliably crawls out of noise), a **bug** (a rare fluke under knife-edge
> tuning), or **unresolved** (it swings on arbitrary parameters and never
> converges)?

Each verdict must be **earned from data, never hardcoded.**

---

## The two engines

### Engine 1 — the open-ended soup (the real frontier)

[BFF](pot/bff.py) is a tiny self-modifying Brainfuck variant where *program ==
data*. Two random tapes are concatenated so they can read and write into each
other during an interaction; occasionally a byte mutates; nothing else. **No
selection.** We only *watch* — for the signature of a replicator that we never
wrote spreading through the soup.

Metrics (all observed, none optimized): `repl_rate`, `unique_ratio`,
`top_share`, `entropy`, and `near_repl` (a hamming-similarity early-warning for
*partial* replicators). See [`pot/soup.py`](pot/soup.py).

Status: the VM and metrics are verified. Whether a replicator actually emerges
in a given parameter regime is the **genuinely unsolved** part — the reason the
interpreter is ported to Rust ([`rust/src/lib.rs`](rust/src/lib.rs)) and swept
across cores and seeds.

### Engine 2 — the closed baseline (honesty control / extinction anchor)

[`pot/baseline.py`](pot/baseline.py): agents evolve a lookup-table policy to
exploit a hidden `cue → food` map (no lifetime learning — adaptation is purely
evolutionary). It has a *known* optimum, so it is **only** a sanity baseline and
the extinction anchor:

- **STRUCTURED** world → most seeds adapt, majority of the hidden map recovered,
  capture ≫ chance.
- **NULL** world (no structure) → **every seed goes extinct.** If a
  structureless world sustains "life," the harness is leaking structure and the
  whole run is marked **VOID**.

---

## Non-negotiable honesty controls

1. **Scrambled control.** Whenever an emergence metric fires on a real run, an
   identical run on a *scrambled/structureless* control must **not** fire. If it
   does, the signal is a metric artifact — flagged, not reported as emergence.
   First-class in the harness ([`pot/experiment.py`](pot/experiment.py)).
2. **Extinction anchor.** In the closed baseline, the null condition must go
   extinct. A null that sustains life voids the run.
3. **Verify before claiming.** VM primitives get unit tests
   ([`tests/test_bff.py`](tests/test_bff.py)); honesty controls get their own
   tests ([`tests/test_honesty.py`](tests/test_honesty.py)). No "it works"
   without an execution log.
4. **Seeded, deterministic, checkpointed** everywhere. Every figure regenerates
   from a checkpoint.

---

## Quickstart

```bash
# 1. build the Rust interpreter into your environment (falls back to pure
#    Python automatically if you skip this)
pip install maturin
maturin develop --release

# 2. run the primitive + honesty tests
pytest

# 3. a short real soup run + baseline, then the verdict harness
python -m pot.experiment --quick

# 4. regenerate the static site from real checkpoints
python web/build_site.py
```

`pot.experiment` writes `results.json` and appends to `ledger.json`
(predict-before-run). `web/build_site.py` embeds those real checkpoints into a
single self-contained `web/index.html` — no build step, GitHub Pages ready.

## Real-world origin (`--cosmic-seed`)

A world can draw its first breath from *actual physics* instead of a chosen
integer. [`pot/cosmos.py`](pot/cosmos.py) harvests real physical indeterminism —
hardware thermal/timing entropy, nanosecond clock jitter, the machine's live
thermodynamic state, and (best-effort) a physics lab's randomness beacon (NIST)
plus atmospheric radio noise (random.org) — mixes it into a seed, and **logs the
seed and its provenance.** So a cosmic run's *origin* is the real universe's
noise while its *record* stays fully reproducible.

```bash
python -m pot.cosmos                       # show which real sources are reachable
python -m pot.live --cosmic-seed           # a showcase soup born from real physics
python -m pot.experiment --cosmic-seed     # root the science seeds in real physics
```

Honest scope: this makes the *origin* real; it does not, by itself, make
organisms "know" the world (noise is noise). Binding them to real *structure*
needs a real *signal* in their environment — the shared channel (issue #14),
seeded by `cosmos.physical_sample()`. Microphone/camera adapters exist but are
**off** by default (privacy — they need the library *and* explicit opt-in).

## Layout

```
rust/          fast BFF interpreter (pyo3 + maturin, rayon-parallel)
pot/bff.py     pure-python VM — reference + fallback + correctness oracle
pot/soup.py    open-ended soup engine + emergence metrics
pot/baseline.py closed-form pot (honesty control / extinction anchor)
pot/experiment.py multi-seed sweeps, scrambled control, verdict logic
pot/ledger.py  predict-before-run, log predicted vs actual
tests/         primitive correctness + honesty controls
web/           build_site.py -> single static index.html (GitHub Pages)
```

## Deploy & compute

- **Frontend:** GitHub Pages (the generated `web/index.html` is fully
  self-contained — no external assets, no build step). CI builds and deploys it
  on every push to `main`.
- **Compute is local and polite.** Sweeps run on your own machine but throttle
  themselves: workers drop to below-normal scheduling priority
  ([`pot/util.py`](pot/util.py)) and reserve half your cores, so the OS hands
  foreground apps the CPU the instant they want it and the soup only fills the
  spare cycles. Heavy runs slow down when you need the machine and speed back up
  when you don't — no babysitting.

  ```bash
  python -m pot.sweep --epochs 20000 --seeds 4      # polite by default
  python -m pot.sweep --workers 2 --epochs 2000000  # a deep, near-invisible run
  ```

  A managed free tier was considered and dropped: free workers spin down when
  idle and can't hold a multi-million-epoch run, and this project's own rule is
  that a personal machine shouldn't be a 24/7 grind host — so compute stays
  local, self-throttling, and checkpointed instead. **Never Vercel.**

## What is *not* settled

This engine can tell you whether a replicator emerges *in the regimes it can
afford to sweep*. It cannot settle the cosmic-scale question of whether
intelligence is a feature of physics in general. The baseline is an anchor, not
a proof. The caveats section of the generated site states plainly what is
narrow, what is the anchor, and what stays open.

## License

MIT.
