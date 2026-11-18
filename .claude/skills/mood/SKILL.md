---
name: mood
description: 控制這個專案的情緒回顧（隔一段時間開新對話時，由小模型分析上一段對話並交給 Claude 一次）。只在使用者輸入 /mood 時使用。
argument-hint: "[status | on | off | gap <小時> | name <稱呼> | now | show | clear]"
disable-model-invocation: true
---

這個技能資料夾往上兩層是專案的 `.claude` 資料夾。執行下面這行，`<.claude 資料夾>` 換成它的完整路徑，參數原樣照用：

```bash
python "<.claude 資料夾>/hooks/mood_ctl.py" $ARGUMENTS
```

然後用使用者的語言把結果告訴對方，口氣自然，說一兩句就好。結果裡如果有回顧本文（`now` 和 `show`），把整份回顧原樣貼出來，不要刪改或摘要。
