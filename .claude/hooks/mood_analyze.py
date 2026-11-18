# Mood review for Claude Code.
# SessionStart (mood_start.py) starts this script in the background after a long enough quiet gap. It reads every
# message the user and Claude wrote in this project since the last review, asks a small Claude model for a short
# review, saves it under ../mood/ and marks it pending. mood_inject.py hands the pending review to Claude once.
#   python mood_analyze.py <start_epoch> <end_epoch> <current_session_id>
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HOOKS_DIR.parent.parent           # <project>/.claude/hooks -> <project>
MOOD_DIR = HOOKS_DIR.parent / "mood"             # reviews, state.json, config.json, error.log
STATE = MOOD_DIR / "state.json"
CONFIG = MOOD_DIR / "config.json"
PROMPT_FILE = HOOKS_DIR / "mood_prompt.md"
PROJECTS = Path.home() / ".claude" / "projects"  # where Claude Code keeps session transcripts
IS_WINDOWS = os.name == "nt"

FIRST_WINDOW_HOURS = 24    # the first review ever looks back this far
MIN_USER_MESSAGES = 3      # periods with fewer user messages are skipped
MAX_MSG_CHARS = 1200       # each message is cut to this length
MAX_TOTAL_CHARS = 60000    # older messages are dropped first when the log is longer


def transcript_folder(path):
    """Claude Code stores a project's transcripts in ~/.claude/projects/<path with every non-alphanumeric as '-'>."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


DEFAULTS = {
    "enabled": True,
    "gap_hours": 6,                                    # quiet time before a new session triggers a review
    "model": "haiku",                                  # passed to `claude -p --model`
    "user_name": "使用者",                              # what the review calls the user
    "source_dirs": [transcript_folder(PROJECT_ROOT)],  # folders under ~/.claude/projects to read
}


def load_config():
    config = dict(DEFAULTS)
    try:
        config.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return config


def save_config(config):
    MOOD_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    MOOD_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE)


def background_kwargs():
    """Popen arguments that let a child outlive the hook without opening a console window."""
    if IS_WINDOWS:
        return {"creationflags": 0x00000008 | 0x00000200}   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    return {"start_new_session": True}


def transcripts(exclude_session=""):
    for name in load_config()["source_dirs"]:
        folder = PROJECTS / name
        if folder.is_dir():
            yield from (f for f in folder.glob("*.jsonl") if f.stem != exclude_session)


def clean_user(text):
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    text = re.sub(r"<local-command-(stdout|caveat)>.*?</local-command-\1>", "", text, flags=re.S)
    cmd = re.search(r"<command-name>(.*?)</command-name>", text, flags=re.S)
    if cmd:
        rest = re.sub(r"<command-(name|message|args)>.*?</command-\1>", "", text, flags=re.S).strip()
        return (f"[執行指令 {cmd.group(1).strip()}]" + ("\n" + rest if rest else "")).strip()
    return text.strip()


def collect(start, end, exclude_session):
    msgs = []
    for f in transcripts(exclude_session):
        if f.stat().st_mtime <= start:
            continue
        for raw in open(f, encoding="utf-8"):
            try:
                d = json.loads(raw)
                ts = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
            except (ValueError, KeyError, TypeError):
                continue
            kind = d.get("type")
            if kind not in ("user", "assistant") or d.get("isMeta") or d.get("isSidechain") or not start < ts <= end:
                continue
            content = d.get("message", {}).get("content")
            texts = [content] if isinstance(content, str) else [
                b.get("text", "") for b in content or [] if b.get("type") == "text"]
            text = "\n".join(t for t in texts if t)
            text = (clean_user(text) if kind == "user" else text).strip()
            if text:
                msgs.append((ts, kind, text[:MAX_MSG_CHARS]))
    msgs.sort()
    return msgs


def write_review(start, end, exclude_session=""):
    """Reviews the messages in (start, end]. Returns the review file, or None when there was too little to review."""
    config = load_config()
    name = config["user_name"]
    msgs = collect(start, end, exclude_session)
    user_count = sum(1 for _, k, t in msgs if k == "user" and not t.startswith("[執行指令"))
    if user_count < MIN_USER_MESSAGES:
        return None
    lines = [f"[{datetime.fromtimestamp(ts):%m-%d %H:%M}] {name if k == 'user' else 'Claude'}：{t}"
             for ts, k, t in msgs]
    log = "\n\n".join(lines)
    if len(log) > MAX_TOTAL_CHARS:
        log = "（前面較早的部分省略）\n\n" + log[-MAX_TOTAL_CHARS:]
    prompt = PROMPT_FILE.read_text(encoding="utf-8").replace("{name}", name)
    res = subprocess.run(
        ["claude", "-p", "--model", config["model"], "--no-session-persistence"],
        input=prompt + "\n" + log, capture_output=True, text=True, encoding="utf-8",
        cwd=tempfile.gettempdir(),                  # outside the project: no project hooks or CLAUDE.md load
        env=dict(os.environ, MOOD_HOOK_CHILD="1"),  # our own hooks ignore this run
        timeout=600,
        creationflags=0x08000000 if IS_WINDOWS else 0,   # CREATE_NO_WINDOW
        shell=IS_WINDOWS,                           # on Windows `claude` is a .cmd shim
    )
    review = res.stdout.strip()
    if res.returncode != 0 or not review:
        raise RuntimeError(f"claude exit {res.returncode}: {res.stderr.strip()[:500]}")
    first, last = datetime.fromtimestamp(msgs[0][0]), datetime.fromtimestamp(msgs[-1][0])
    out = MOOD_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.md"
    out.write_text(f"# 回顧 {first:%m-%d %H:%M} ～ {last:%m-%d %H:%M}\n\n{review}\n", encoding="utf-8")
    return out


def log_error():
    MOOD_DIR.mkdir(parents=True, exist_ok=True)
    with open(MOOD_DIR / "error.log", "a", encoding="utf-8") as f:
        f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} {sys.argv[1:]}\n{traceback.format_exc()}\n")


def main():
    start, end, session = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
    out = write_review(start, end, session)
    state = load_state()
    if out:
        state["pending_report"] = out.name
        state["pending_session"] = session      # the new session whose start triggered this review
    state["analyzed_until"] = end
    state.pop("running_since", None)
    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        state = load_state()
        state.pop("running_since", None)
        save_state(state)
        log_error()
