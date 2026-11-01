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

## 日本株スイング候補（swing_scan.py）

現物・短期（数日〜1週間）の**買い候補**を、週足+日足のダウ理論とスーパートレンドで毎営業日抽出します。

- 実行: `.github/workflows/swing_scan.yml`（平日17:00 JST）。出力は `output/swing_candidates.json`、採点用の履歴は `output/swing_log.csv`
- 余力・許容損失は**公開リポジトリに書かず**、Secrets の `SWING_CAPITAL` / `SWING_MAX_LOSS`（円）で渡します
- 絞り込み: 株価≤余力/100株、ATR%≥2.5、20日平均売買代金≥2億円（`swing_config.json`）
- 損切り=直近確定スイング安値−0.2ATR、押し目指値=直近レッグの50%戻し、RR=直近高値まで（RR≥1のみ）
- 決算・ニュースは未確認（別工程で確認する前提）
- ローカル検算: `python tests/test_swing_scan.py`（ネットワーク不要）
- `indicators/dow_theory.py` に `dedupe_ties`（既定False＝従来どおり）を追加。同値の隣接ピボットを1点にまとめます
