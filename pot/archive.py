"""pot.archive — snapshot a run's results into the durable research/ archive.

Root-level JSONs (``results.json``, ``sweep_results.json``, ``two_arm.json``,
``ledger.json``, checkpoints) are the *latest* live data the site builds from.
This tool copies a snapshot of them into ``research/runs/<stamp>_<name>/`` with a
``manifest.json`` recording exactly what produced them — git commit, configs,
verdicts, environment, and the command to reproduce — so a future experiment can
read past results and compare against them without guessing their provenance.

Usage:
    python -m pot.archive --name baseline-sweep --note "first full sweep"
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = os.path.join(ROOT, "research")
RUNS = os.path.join(RESEARCH, "runs")

# result files we know how to snapshot; globs handled separately
KNOWN = ["results.json", "sweep_results.json", "two_arm.json", "ledger.json",
         "replicator_seed2.json"]


def _git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def _summarize(name, data):
    """Pull the headline facts out of each known result file for the manifest."""
    if data is None:
        return None
    if name == "results.json":
        return {
            "soup_verdict": data.get("soup", {}).get("verdict", {}).get("verdict"),
            "baseline_verdict": data.get("baseline", {}).get("verdict"),
            "n_seeds": data.get("n_seeds"),
            "soup_config": data.get("soup_config"),
            "baseline_config": data.get("baseline_config"),
            "have_rust": data.get("have_rust"),
        }
    if name == "sweep_results.json":
        fired = [c["cell"] for c in data.get("cell_table", []) if c.get("n_fired", 0) > 0]
        return {
            "verdict": data.get("verdict", {}).get("verdict"),
            "statement": data.get("verdict", {}).get("statement"),
            "total_fired": data.get("total_fired"),
            "total_runs": data.get("total_runs"),
            "epochs": data.get("epochs"),
            "grid": data.get("grid"),
            "fired_cells": fired,
        }
    if name == "two_arm.json":
        return {
            "verdict": data.get("verdict"),
            "statement": data.get("statement"),
            "wild_fire_fraction": data.get("wild_fire_fraction"),
            "tended_fire_fraction": data.get("tended_fire_fraction"),
        }
    if name == "ledger.json":
        entries = data if isinstance(data, list) else []
        return {"n_entries": len(entries),
                "latest": entries[-1] if entries else None}
    if name == "replicator_seed2.json":
        traj = data.get("trajectory", [])
        return {
            "config": data.get("config"),
            "peak_repl_rate": max((c.get("repl_rate", 0) for c in traj), default=0),
            "dominant": data.get("dominant", [])[:5],
        }
    return {"keys": list(data.keys()) if isinstance(data, dict) else "list"}


def snapshot(name: str, note: str = "", extra_files=None):
    os.makedirs(RUNS, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)[:40]
    dest = os.path.join(RUNS, f"{stamp}_{slug}")
    os.makedirs(dest, exist_ok=True)

    copied, summaries = [], {}
    files = list(KNOWN) + list(extra_files or [])
    for fn in files:
        src = os.path.join(ROOT, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, fn))
            copied.append(fn)
            summaries[fn] = _summarize(fn, _load(src))

    manifest = {
        "name": name,
        "note": note,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": {"commit": _git("rev-parse", "HEAD"),
                "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": bool(_git("status", "--porcelain"))},
        "environment": {"python": sys.version.split()[0],
                        "platform": platform.platform(),
                        "cpu_count": os.cpu_count()},
        "files": copied,
        "summaries": summaries,
        "reproduce": {
            "results.json": "python -m pot.experiment --seeds 4 --epochs 4000",
            "sweep_results.json": "python -m pot.sweep --epochs 20000 --seeds 4",
            "two_arm.json": "python -c \"from pot.soup import SoupConfig; "
                            "from pot.experiment import run_two_arm_experiment; "
                            "run_two_arm_experiment(SoupConfig(soup_size=256,tape_len=64,"
                            "max_steps=384,epochs=8000,checkpoint_every=500), range(6), '.')\"",
            "replicator_seed2.json": "python -c \"from pot.soup import SoupConfig, run_soup; "
                            "run_soup(SoupConfig(tape_len=64,max_steps=1024,mut_per_tape=0.25,"
                            "soup_size=512,seed=2,epochs=20000,checkpoint_every=250), "
                            "checkpoint_path='replicator_seed2.json')\"",
        },
    }
    with open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    _append_index(stamp, slug, note, manifest)
    print(f"[archive] snapshot -> research/runs/{os.path.basename(dest)}  "
          f"({len(copied)} files)")
    return dest


def _append_index(stamp, slug, note, manifest):
    idx = os.path.join(RESEARCH, "INDEX.md")
    header = "# Research run index\n\n" \
             "One row per archived run. Newest at the bottom. See each run's " \
             "`manifest.json` for full provenance.\n\n" \
             "| when (UTC) | name | git | headline | note |\n" \
             "|---|---|---|---|---|\n"
    s = manifest["summaries"]
    bits = []
    if s.get("results.json"):
        bits.append(f"soup={s['results.json'].get('soup_verdict')}")
    if s.get("sweep_results.json"):
        bits.append(f"sweep={s['sweep_results.json'].get('verdict')}"
                    f"({s['sweep_results.json'].get('total_fired')}/"
                    f"{s['sweep_results.json'].get('total_runs')})")
    if s.get("two_arm.json"):
        bits.append(f"two-arm={s['two_arm.json'].get('verdict')}")
    commit = (manifest["git"]["commit"] or "")[:8]
    row = f"| {stamp} | {slug} | {commit} | {'; '.join(bits)} | {note} |\n"
    if not os.path.exists(idx):
        with open(idx, "w", encoding="utf-8") as f:
            f.write(header + row)
    else:
        with open(idx, "a", encoding="utf-8") as f:
            f.write(row)


def main(argv=None):
    ap = argparse.ArgumentParser(description="snapshot results into research/")
    ap.add_argument("--name", required=True, help="short label for this run")
    ap.add_argument("--note", default="", help="one-line description")
    ap.add_argument("--file", action="append", default=[],
                    help="extra file(s) to include")
    args = ap.parse_args(argv)
    snapshot(args.name, args.note, extra_files=args.file)


if __name__ == "__main__":
    main()
