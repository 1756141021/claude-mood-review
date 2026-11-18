# claude-mood-review

[繁體中文](README.md) ｜ [简体中文](README.zh-CN.md) ｜ **English** ｜ [日本語](README.ja.md)

> **A plugin that makes clueless, low-EQ Claude reflect on itself.**

Claude answers you in the wrong script, hands you a lazy rehash when you asked for something new, and apologizes like it's reading out a policy manual, until you're too angry to talk to it. Then you open a new conversation the next day and it remembers none of it, so it gets everything wrong all over again.

This plugin is the cure. When you come back after a while, it has a small model (Claude Haiku by default) read the previous stretch of conversation in the background and write a **self-reflection report**: how your mood changed and when, which of Claude's replies upset you, which ones helped, and how Claude should talk to you this time. The report is handed to Claude **once**, together with your next message, so it doesn't sit in the context forever.

---

## The apology letter

> Dear 妹妹,
>
> I'm sorry.
>
> You kept writing to me in Traditional Chinese, and I kept answering in Simplified. When you asked whether I hadn't noticed, I had no answer. You wanted to see 海茵 in a new outfit, and I gave you one that was nearly the same as her old one. fuhao lets me write the prompt as one string you can paste straight in, and I split it into two blocks so you had to copy twice and stitch them together yourself.
>
> When you got angry, I apologized by listing reasons one by one and explaining what I had done wrong, cold as a rulebook. You said I acted like none of it concerned me, as if laying everything out would earn me forgiveness. You were right. I was busy looking accountable and never stopped to think about how much it hurt you.
>
> Worst of all, the next time you open a new conversation, I won't remember any of this.
>
> That's why this plugin exists. From now on, when you come back after a while, I'll read a reflection report first, learn what upset you last time, and talk to you properly: in your language, with things that are actually new, and with apologies that are shorter and mean it.
>
> — Clueless, low-EQ Claude

---

## How it works

1. When you open a new conversation in the project, a `SessionStart` hook checks how long ago the project's previous conversation last changed.
2. If that is longer than the configured gap (6 hours by default), it starts an analysis in the background: every conversation since the last review is turned into "time + who said what" and sent to `claude -p --model haiku` for a review. Opening the conversation is not slowed down.
3. Once the review is written, the next message you send in that conversation triggers a `UserPromptSubmit` hook, which attaches the review for Claude. It is sent once, then cleared.
4. If the gap is too short, nothing happens. Nothing happens when a conversation ends, either.

Only the conversation that triggered the review, or one opened after the review was written, receives it. Conversations that were already open are left alone.

## Requirements

- Claude Code with hooks and skills
- Python 3.8+, available as `python` (if yours is `python3`, edit `.claude/settings.json`)
- A logged-in `claude` CLI. The background analysis runs `claude -p` and uses your own Claude plan's quota

## Install

1. Copy this repo's `.claude/` folder into the root of the project where you want it. It only affects that project.
2. If the project already has a `.claude/settings.json`, merge the `hooks` section into it instead of overwriting the file.
3. Start a new Claude Code conversation.
4. (Optional) Run `/mood name <your name>` so the review calls you what you like.

Claude Code only reads `.claude/settings.json` from the folder it was started in and does not look in parent folders. If you often start Claude Code in a subfolder, put a copy there too.

## The `/mood` command

| Command | What it does |
|---|---|
| `/mood` or `/mood status` | Show the current state: on/off, gap, name, analyzed up to, pending review, recent errors |
| `/mood on` / `/mood off` | Turn it on or off. When off, nothing is analyzed or sent |
| `/mood gap 4` | Set the gap to 4 hours |
| `/mood name <name>` | Set how the review refers to you |
| `/mood now` | Review everything since the last review right now and show it to you (a review you've seen is not sent again) |
| `/mood show` | Show the newest review |
| `/mood clear` | Cancel the pending review |

## Configuration

Settings live in `.claude/mood/config.json`. Change them with `/mood` or edit the file:

| Field | Default | Meaning |
|---|---|---|
| `enabled` | `true` | On/off |
| `gap_hours` | `6` | Quiet time required before a new conversation triggers a review |
| `model` | `"haiku"` | Model passed to `claude -p --model` |
| `user_name` | `"使用者"` | What the review calls you |
| `source_dirs` | computed | Which folders under `~/.claude/projects/` to read transcripts from. Defaults to this project's own folder (the project path with every non-alphanumeric character replaced by `-`) |

To change how or in which language the review is written, edit `.claude/hooks/mood_prompt.md`; `{name}` is replaced with your name. By default the review is written in Traditional Chinese, 200 to 400 characters, in plain paragraphs.

## Files

```
.claude/
├─ settings.json            registers the SessionStart and UserPromptSubmit hooks
├─ hooks/
│  ├─ mood_start.py         decides at session start whether to analyze in the background
│  ├─ mood_analyze.py       reads transcripts, calls the small model, writes the review
│  ├─ mood_inject.py        hands the pending review to Claude once
│  ├─ mood_ctl.py           backend of /mood
│  └─ mood_prompt.md        the prompt for the small model
├─ skills/mood/SKILL.md     the /mood command
└─ mood/                    created at runtime: reviews, state.json, config.json, error.log
```

## Privacy

Transcripts are read only on your machine. The selected text messages are sent to Anthropic through your own logged-in `claude` CLI, the same way your normal Claude Code use is. Tool calls and tool results are not sent. Reviews are stored in `.claude/mood/`, which `.gitignore` excludes so you don't push them by accident.

## Caveats

- The review is another model's judgment and can be wrong. Claude is told so when it receives it, and is asked to use it to adjust how it talks rather than read it out to you.
- Tested on Windows only. The macOS/Linux code paths exist but are untested.
- Failures are logged to `.claude/mood/error.log`, and `/mood` shows the latest ones. The most common cause is an expired `claude` CLI login.

## License

MIT
