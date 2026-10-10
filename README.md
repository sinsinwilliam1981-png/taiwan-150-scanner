# 小白投資 C 方案：台股 150 策略掃描

可部署到 GitHub Actions + GitHub Pages 的免費優先方案。後端向 FinMind 抓取臺灣50與臺灣中型100共 150 檔日 OHLCV，通過 **每檔至少 120 個交易日、150/150 全數成功** 的閘門後才發布技術指標及候選結果；任何一檔失敗時，公開 JSON 不含部分候選，避免把不完整掃描誤認成完整排名。

## 已實作

- FinMind `TaiwanStockPrice` 後端、重試、429/錯誤記錄；Token 僅從環境變數讀取。
- 50/100/跨指數無重複的成分股閘門。`config/constituents.meta.json` 保存來源、生效日與 0050/0051 官方投信交叉核對日。
- MA5/10/20/60、布林帶、RSI14、20日量比、20日報酬、MA20乖離、120日價格位置。
- 透明、可調整的六條件加權策略；結果分為候選、接近觸發、觀察。
- 靜態搜尋/篩選頁面；「手動掃描」導向 Actions 頁面，由登入 GitHub 的使用者按 **Run workflow**，前端不含 PAT/API Token。
- 週一至週五台北 18:00 排程、日期版歷史 JSON 與 `latest.json`。
- 單元測試與 GitHub Pages workflow。

## 部署

1. 建立 GitHub repository，將本專案推到 `main`。公開 repository 的標準 GitHub-hosted runner 不計費；私人 repository 受帳號每月免費分鐘與儲存額度限制。
2. 到 FinMind 註冊並取得 Token。Repository → **Settings → Secrets and variables → Actions → New repository secret**，名稱填 `FINMIND_TOKEN`。不要把值放進 `.env.example`、HTML、JavaScript 或任何 commit。
3. Repository → **Settings → Pages → Source** 選 **GitHub Actions**，手動執行 `Deploy static site` 一次。
4. 到 **Actions → Taiwan 150 scan → Run workflow** 做首次實測。成功後頁面才會從「尚未執行」變成完整結果。
5. 若預設分支不是 `main`，同步修改 `pages.yml`。若 branch protection 禁止 bot push，需允許 GitHub Actions 寫入或改用 PR/外部儲存方案。

## 本機執行

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FINMIND_TOKEN="你的 Token"
pytest -q
python -m scanner.run
python -m http.server 8000 --directory site
```

瀏覽 `http://localhost:8000`。本機 `.env` 已由 `.gitignore` 排除；程式不會自行讀 `.env`，請使用環境變數。

## 排程、UTC 與免費限制

- 臺北全年 UTC+8、沒有日光節約時間；`0 10 * * 1-5` 固定對應週一至週五 18:00 台北時間，不需夏令/冬令切換。
- GitHub 明確說明 `schedule` 在高負載時可能延遲，尤其整點；本需求指定 18:00，因此保留整點。若可接受 18:07，可改為 `7 10 * * 1-5` 降低尖峰延遲風險。
- Scheduled workflow 只在預設分支執行；公開 repo 若 60 天無活動，GitHub 可能停用 schedule。定期確認 Actions 狀態，或由真正的 repo 活動維持啟用。
- GitHub Actions 不是即時排程器，不保證 18:00:00 準時開始。FinMind 也可能尚未完成當日資料更新；閘門會阻止不完整結果發布。
- FinMind 官方目前說明：有 Token 600 次/小時，無 Token 300 次/小時。本流程每次約 150 次，仍可能受服務端政策、流量與單次 timeout 影響。
- GitHub Pages 是公開靜態託管：`site/data/*.json` 會公開，請勿放任何 secret 或個人資料。

## 成分股維護

目前清單依 2026-09-21 生效的官方定審結果，並以元大投信 0050/0051 在 2026-10-08 的完整持股頁交叉核對。ETF 持股可能含現金、期貨或暫時追蹤差異，不能取代官方指數公告。

每次富時臺灣指數系列季度審核後：

1. 依 TWSE/TIP 正式公告更新 `config/constituents.csv` 與 `config/constituents.meta.json`。
2. 執行 `pytest -q`；50、100、總計 150 唯一代號任一不符即失敗。
3. 再用 0050/0051 投信完整持股頁交叉核對並記錄日期；不要使用只顯示前十大持股的二手網站。

## 尚未聲稱完成的事

- 這份交付物未使用你的 FinMind Token，也未推到你的 GitHub，因此尚未做真實 150 檔 API、GitHub cron、Pages 公開網址或 bot push 的端到端雲端實測。
- 「ChatGPT 自動報告」本版實作的是可由 ChatGPT/其他程式讀取的結構化 JSON 與人類可讀網頁，沒有把 OpenAI API key 放入流程，也不會自動發訊息到 ChatGPT。若要主動通知，需要另選 Email/LINE/Slack/GitHub Issue 等目的地及對應秘密金鑰。
- 策略是技術篩選規則，不代表預測或投資建議；未含交易成本、滑價、存活者偏差與回測績效。

## 官方參考

- FinMind Quick Start: https://finmind.github.io/en/quickstart/
- TWSE 指數系列: https://www.twse.com.tw/zh/indices/indices/series.html
- GitHub Actions schedule: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- GitHub Actions billing: https://docs.github.com/en/actions/concepts/billing-and-usage
