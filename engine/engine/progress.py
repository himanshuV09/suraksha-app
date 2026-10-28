"""Progress reporting for long-running commands.

The desktop app reads the engine's stderr line by line. A line of the form

    @@PROGRESS {"stage": "...", "done": 120, "total": 3328, "message": "..."}

is shown as a progress bar; every other stderr line goes to the log.
Reports are throttled so a tight loop cannot flood the pipe.
"""
import json
import sys
import time

PREFIX = "@@PROGRESS "
MIN_INTERVAL = 0.25  # seconds between reports for the same stage

_last_report = {}


def report(stage, done=None, total=None, message="", force=False):
    """Report progress of ``stage``; cheap enough to call in hot loops."""
    now = time.monotonic()
    finished = total is not None and done is not None and done >= total
    if not (force or finished) and now - _last_report.get(stage, 0.0) < MIN_INTERVAL:
        return
    _last_report[stage] = now
    payload = {"stage": stage, "done": done, "total": total, "message": message}
    try:
        sys.__stderr__.write(PREFIX + json.dumps(payload) + "\n")
        sys.__stderr__.flush()
    except (AttributeError, OSError, ValueError):
        pass  # no stderr (e.g. embedded): progress is optional
