"""pot.ledger — predict-before-run discipline.

Before an experiment runs, we write down what we *expect* to happen and why.
After it runs, we write down what actually happened and whether the prediction
held. The point is to keep ourselves honest: a wrong prediction, faithfully
recorded, is worth more than a right one invented after the fact.

Entries accumulate in ``ledger.json`` (a JSON list). Each entry:

    {
      "name": "...",
      "predicted_at": "ISO-8601",
      "prediction": {...},          # arbitrary structured expectation
      "rationale": "...",
      "recorded_at": "ISO-8601",    # filled in after the run
      "actual": {...},              # arbitrary structured result
      "hits": [ {"key":..., "predicted":..., "actual":..., "ok": bool} ],
      "verdict": "..."
    }
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_entry(name: str, prediction: dict, rationale: str) -> dict:
    """Create a prediction entry *before* running the experiment."""
    return {
        "name": name,
        "predicted_at": _now(),
        "prediction": dict(prediction),
        "rationale": rationale,
        "recorded_at": None,
        "actual": None,
        "hits": None,
        "verdict": None,
    }


def finalize(entry: dict, actual: dict, verdict: str,
             checks: "list[tuple]" | None = None) -> dict:
    """Fill in the actual outcome and score predicted-vs-actual checks.

    ``checks`` is a list of ``(key, predicted, actual, ok)`` tuples describing
    which predictions held. It is recorded verbatim so a reader can see exactly
    where we were right and wrong.
    """
    entry = dict(entry)
    entry["recorded_at"] = _now()
    entry["actual"] = dict(actual)
    entry["verdict"] = verdict
    if checks is not None:
        entry["hits"] = [
            {"key": k, "predicted": p, "actual": a, "ok": bool(ok)}
            for (k, p, a, ok) in checks
        ]
    return entry


def append(path: str, entry: dict) -> None:
    """Append an entry to the JSON-list ledger at ``path`` (created if absent)."""
    data = load(path)
    data.append(entry)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
