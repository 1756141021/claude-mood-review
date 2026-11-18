# Backend of the /mood command.
#   python mood_ctl.py [status | on | off | gap <hours> | name <name> | now | show | clear]
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mood_analyze import (FIRST_WINDOW_HOURS, MOOD_DIR, load_config, load_state, save_config, save_state,
                          write_review)

USAGE = "用法：/mood [status | on | off | gap <小時> | name <稱呼> | now | show | clear]"


def fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "還沒有"


def reviews():
    return sorted(MOOD_DIR.glob("20*.md")) if MOOD_DIR.exists() else []


def status():
    config, state = load_config(), load_state()
    print(f"情緒回顧：{'開啟' if config['enabled'] else '關閉'}")
    print(f"間隔：{config['gap_hours']:g} 小時")
    print(f"稱呼：{config['user_name']}　模型：{config['model']}")
    print(f"讀取的對話資料夾：{', '.join(config['source_dirs'])}")
    print(f"已分析到：{fmt(state.get('analyzed_until'))}")
    print(f"待送出的回顧：{state.get('pending_report') or '沒有'}")
    print(f"最新一份回顧：{reviews()[-1].name if reviews() else '沒有'}")
    if state.get("running_since") and time.time() - state["running_since"] < 900:
        print("背景分析：正在進行")
    err = MOOD_DIR / "error.log"
    if err.exists():
        tail = err.read_text(encoding="utf-8").strip().splitlines()[-3:]
        print("最近的錯誤：\n" + "\n".join(tail))


def main(args):
    cmd = args[0].lower() if args else "status"
    config, state = load_config(), load_state()
    if cmd == "status":
        status()
    elif cmd in ("on", "off"):
        config["enabled"] = cmd == "on"
        save_config(config)
        print(f"情緒回顧已{'開啟' if config['enabled'] else '關閉'}。")
    elif cmd == "gap":
        try:
            hours = float(args[1])
            assert hours > 0
        except (IndexError, ValueError, AssertionError):
            print("用法：/mood gap <小時>，例如 /mood gap 4")
            return
        config["gap_hours"] = hours
        save_config(config)
        print(f"間隔改成 {hours:g} 小時。")
    elif cmd == "name":
        if len(args) < 2:
            print("用法：/mood name <稱呼>，例如 /mood name 妹妹")
            return
        config["user_name"] = " ".join(args[1:])
        save_config(config)
        print(f"回顧裡會稱呼你「{config['user_name']}」。")
    elif cmd == "now":
        end = time.time()
        start = state.get("analyzed_until") or end - FIRST_WINDOW_HOURS * 3600
        out = write_review(start, end)
        state = load_state()
        state["analyzed_until"] = end
        state.pop("pending_report", None)        # shown right here, so it is not sent again later
        state.pop("pending_session", None)
        save_state(state)
        if out:
            print(out.read_text(encoding="utf-8"))
        else:
            print(f"從 {fmt(start)} 到現在的對話太少，沒有寫回顧。")
    elif cmd == "show":
        print(reviews()[-1].read_text(encoding="utf-8") if reviews() else "還沒有任何回顧。")
    elif cmd == "clear":
        had = state.pop("pending_report", None)
        state.pop("pending_session", None)
        save_state(state)
        print(f"已取消待送出的回顧 {had}。" if had else "沒有待送出的回顧。")
    else:
        print(USAGE)


if __name__ == "__main__":
    main(sys.argv[1:])
