# SessionStart hook: if the user comes back after `gap_hours` of quiet, start mood_analyze.py in the background on
# the conversations since the last review. Prints nothing, so it adds nothing to Claude's context.
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if os.environ.get("MOOD_HOOK_CHILD"):
    sys.exit(0)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mood_analyze import (FIRST_WINDOW_HOURS, background_kwargs, load_config, load_state, save_state,
                          transcripts)

config = load_config()
if not config["enabled"]:
    sys.exit(0)

data = json.load(sys.stdin)
if data.get("source") not in ("startup", "resume"):   # ignore /clear and compaction
    sys.exit(0)
session = data.get("session_id", "")

files = list(transcripts(session))
if not files:
    sys.exit(0)
now = time.time()
last = max(f.stat().st_mtime for f in files)
if now - last < float(config["gap_hours"]) * 3600:
    sys.exit(0)

state = load_state()
if now - state.get("running_since", 0) < 900:          # a review is already being written
    sys.exit(0)
start = state.get("analyzed_until") or last - FIRST_WINDOW_HOURS * 3600
if last <= start:
    sys.exit(0)

state["running_since"] = now
save_state(state)
subprocess.Popen(
    [sys.executable, str(Path(__file__).resolve().parent / "mood_analyze.py"), str(start), str(last), session],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
    **background_kwargs(),
)
