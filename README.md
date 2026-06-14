# 📊 Market Analyzer

株価・為替のダウ理論 + スーパートレンド マルチタイムフレーム分析ツール

## 機能

- **ダウ理論**：高値・安値の切り上げ/切り下げを自動判定
- **スーパートレンド**：ATRベースのトレンド方向とBUY/SELLシグナル
- **MTFスコア**：複数タイムフレームの一致度を0〜100でスコア化
- **ピックアップ**：条件を満たした銘柄を自動抽出
- **管理画面**：iPhoneから銘柄・条件をGUIで変更

## ファイル構成

```
├── analyze.py          # メイン分析スクリプト
├── config.json         # 銘柄・条件設定（admin.htmlから変更可能）
├── config_loader.py    # config.json読み込みモジュール
├── config.py           # fallback設定
├── chart.py            # Lightweight Chartsチャート生成
├── report.py           # HTMLレポート生成
├── lw_charts.js        # TradingView Lightweight Charts JS（CDN不要）
├── admin.html          # iPhone対応の管理画面
├── indicators/
│   ├── supertrend.py   # スーパートレンド計算
│   └── dow_theory.py   # ダウ理論判定
├── output/
│   └── report.html     # 生成されるレポート（GitHub Pagesで公開）
└── .github/workflows/
    └── analyze.yml     # GitHub Actions（朝・昼・晩 自動実行）
```

## セットアップ

### 1. リポジトリ作成

```bash
git clone https://github.com/YOUR_NAME/market-analyzer.git
cd market-analyzer
```

### 2. GitHub Pages 有効化

Settings → Pages → Source: `main` ブランチ / `/ (root)`

### 3. Personal Access Token 発行

Settings → Developer settings → Personal access tokens → Fine-grained tokens  
権限: `Contents: Read and Write` / `Actions: Write`

### 4. admin.html を開く

`https://YOUR_NAME.github.io/market-analyzer/admin.html`  
→ リポジトリ名とTokenを入力して設定完了

## 自動実行スケジュール（JST）

| 時刻 | cron |
|------|------|
| 朝 08:00 | `0 23 * * *` |
| 昼 12:00 | `0 3 * * *`  |
| 晩 20:00 | `0 11 * * *` |

`config.json` が更新されたときも自動トリガーされます。

## ローカル実行

```bash
pip install yfinance pandas numpy
python analyze.py
# → output/report.html が生成される
```

## 対応データソース

yfinance（Yahoo Finance）を使用。ティッカー例：
- 為替: `JPY=X` `EURUSD=X`
- 貴金属: `GC=F` `SI=F`
- 日本株: `7203.T`（末尾に `.T`）
- 日経225: `^N225`
