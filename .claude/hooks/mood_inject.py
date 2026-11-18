# UserPromptSubmit hook: hands Claude the pending mood review once, attached to the user's next message, then
# clears it so it is never sent again. Only the session that triggered the review, or one opened after it was
# written, receives it.
import json
import os
import sys
from pathlib import Path

if os.environ.get("MOOD_HOOK_CHILD"):
    sys.exit(0)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mood_analyze import MOOD_DIR, load_config, load_state, save_state

config = load_config()
if not config["enabled"]:
    sys.exit(0)
data = json.load(sys.stdin)
state = load_state()
name = state.get("pending_report")
if not name or not (MOOD_DIR / name).exists():
    sys.exit(0)
report = MOOD_DIR / name
if data.get("session_id") != state.get("pending_session"):
    try:
        opened = Path(data.get("transcript_path", "")).stat().st_ctime
    except OSError:
        opened = 0
    if opened < report.stat().st_mtime:
        sys.exit(0)
review = report.read_text(encoding="utf-8").strip()
state.pop("pending_report")
state.pop("pending_session", None)
save_state(state)

user = config["user_name"]
context = (
    f"{user}隔了一段時間回來。以下是背景程式請另一個 Claude 模型根據{user}上一段時間的對話寫的回顧，"
    f"可能不準。用它調整你對{user}說話的方式，不要原文念出來；"
    f"{user}當時若有身體或情緒上的不舒服，可以自然地關心一句。\n\n" + review
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}))
