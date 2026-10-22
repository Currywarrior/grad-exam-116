# 116 學年度碩士班考試入學報名時程表

網頁：https://currywarrior.github.io/grad-exam-116/

整理四大（台大、清大、陽明交大、成大）、四中（中央、中興、中山、中正）、台科、北科的 116 學年度碩士班考試入學簡章公告、網路報名與筆試日期，以資工相關所為主。

**網頁內容僅供參考，報名前請一定以各校簡章為準。**

## 怎麼更新

- GitHub Actions（`.github/workflows/check.yml`）每天排程執行 `check.py`。排程設在台灣時間 9 點，但 GitHub 免費排程常延後，實際大約在下午 1～2 點跑。
- `check.py` 用 Playwright 打開各校招生頁，找 116 學年度碩士班考試入學簡章；找到就把該校標成已公告，並試著從簡章 PDF 抓報名與筆試日期。
- 有變動時自動 commit `data.json`，網頁（`index.html`）讀這份資料顯示。

## 限制

- 不是即時更新，學校公告後最慢隔天才會出現在網頁上。
- 自動抓到的日期會標「日期待確認」，可能抓錯或漏抓。
- 已公告的學校是人工核對過的資料，程式不會再檢查；學校之後改日期需要手動更新。
- 標「預定」的學校，日期來自學校公布的預定日程表，簡章正式公告後可能變動。

## 手動修改資料

直接編輯 `data.json` 推上 main 即可。每間學校的欄位：

| 欄位 | 說明 |
|---|---|
| `status` | `out` 已公告、`plan` 有預定日程、`none` 尚無消息 |
| `announce` / `announceText` | 簡章公告日（ISO 日期），或無確切日期時的文字 |
| `reg` / `exam` | 報名起訖日、筆試日期（ISO 日期陣列） |
| `release` | 放榜時間 |
| `note` | 備註，可含 HTML |
| `link` | 簡章或公告連結 |

本機測試爬蟲：

```
pip install -r requirements.txt
playwright install chromium
python check.py
```
