"""Daily-overlap activity-log files (GP2, follows ADR-0011 GP2 plan).

Each event is appended to JSON-Lines file(s) named ``events-YYYY-MM-DD.jsonl``. The
overlap window — `[D-1 23:50, D 01:10)` belongs to **both** day D-1 and day D — means
an event near a date boundary lands in two files. We don't dedupe across files: each
copy carries a ``log_date`` field so downstream analysis can either pick one or merge
on ``event_id``.

The handler is intentionally **not** a `logging.Handler` subclass. The request path
calls `emit_event(payload)` directly, which:

  - never raises (file system / permission errors are swallowed — request path stays clean),
  - never blocks on logging config — the directory is created lazily,
  - never touches a global logger or formatter that someone could reconfigure underneath us.

The daily files are intended for:
  - operators who need a per-day audit dump independent of Postgres
  - long-tail forensic queries that don't fit a ``audit_logs`` row
The DB ``audit_logs`` row remains the system of record for in-app surfaces (the Admin
Audit Trail page); both carry the same ``event_id`` so cross-referencing is one join.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# Where to write. Mounted as a host volume in the dev compose.
_DEFAULT_DIR = "/srv/var/log/hybrid-idp"
# What tz the "date file" boundary uses. KST by default to match Korean office hours.
_DEFAULT_TZ = "Asia/Seoul"


def _files_for(ts_local: datetime) -> list[date]:
    """Pick which daily files this event lands in.

    Window per day D is `[D-1 23:50, D+1 01:10)`. So an event at 23:55 belongs in
    both yesterday's file (its own day) and tomorrow's file (next day's window).
    """
    primary = ts_local.date()
    files = [primary]
    t = ts_local.time()
    if t >= dtime(23, 50):
        files.append(primary + timedelta(days=1))
    elif t < dtime(1, 10):
        files.append(primary - timedelta(days=1))
    return files


def emit_event(payload: dict[str, Any]) -> None:
    """Append ``payload`` to today's (and possibly yesterday/tomorrow's) JSON-Lines file.

    Adds ``ts``/``ts_local``/``log_date`` automatically. Caller provides the event-specific
    payload (kind, outcome, actor, metrics, trace_id, event_id, ...). Never raises.
    """
    try:
        log_dir = Path(os.environ.get("EVENTS_LOG_DIR", _DEFAULT_DIR))
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return  # log dir not writable (e.g. read-only fs) → drop the file log; DB is authoritative

    try:
        tz = ZoneInfo(os.environ.get("EVENTS_TZ", _DEFAULT_TZ))
    except Exception:  # noqa: BLE001 — unknown zone
        tz = timezone.utc

    ts_utc = datetime.now(tz=timezone.utc)
    ts_local = ts_utc.astimezone(tz)
    base = {**payload, "ts": ts_utc.isoformat(), "ts_local": ts_local.isoformat()}

    for d in _files_for(ts_local):
        try:
            line = {**base, "log_date": d.isoformat()}
            with (log_dir / f"events-{d.isoformat()}.jsonl").open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            continue  # one file failing shouldn't block the other
