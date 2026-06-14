# ============================================================
#  config.py  - 監視シンボルと分析パラメータの設定
#  ここを編集するだけで監視対象を自由に変更できます
# ============================================================

# ── 監視シンボル定義 ──────────────────────────────────────
# name    : 表示名
# ticker  : yfinanceティッカー
# category: グループ分類
# enabled : False にすると一時的に除外

SYMBOLS = [
    # 貴金属
    {"name": "ゴールド",      "ticker": "GC=F",   "category": "貴金属",   "enabled": True},
    {"name": "シルバー",      "ticker": "SI=F",   "category": "貴金属",   "enabled": True},

    # 為替
    {"name": "USD/JPY",      "ticker": "JPY=X",  "category": "為替",     "enabled": True},
    {"name": "EUR/USD",      "ticker": "EURUSD=X","category": "為替",    "enabled": True},
    {"name": "GBP/USD",      "ticker": "GBPUSD=X","category": "為替",    "enabled": True},

    # 米国株・ETF
    {"name": "S&P500 ETF",   "ticker": "SPY",    "category": "米国株",   "enabled": True},
    {"name": "NASDAQ ETF",   "ticker": "QQQ",    "category": "米国株",   "enabled": True},
    {"name": "Apple",        "ticker": "AAPL",   "category": "米国株",   "enabled": True},
    {"name": "NVIDIA",       "ticker": "NVDA",   "category": "米国株",   "enabled": True},

    # 日本株
    {"name": "日経225",      "ticker": "^N225",  "category": "日本株",   "enabled": True},
    {"name": "トヨタ",        "ticker": "7203.T", "category": "日本株",   "enabled": True},
    {"name": "ソニー",        "ticker": "6758.T", "category": "日本株",   "enabled": True},
    {"name": "三菱UFJ",      "ticker": "8306.T", "category": "日本株",   "enabled": True},
]

# ── マルチタイムフレーム設定 ──────────────────────────────
TIMEFRAMES = [
    {"label": "週足",  "interval": "1wk",  "period": "2y",   "weight": 4},
    {"label": "日足",  "interval": "1d",   "period": "1y",   "weight": 3},
    {"label": "4時間", "interval": "1h",   "period": "60d",  "weight": 2},  # yfinanceは1h最大で60日
    {"label": "1時間", "interval": "1h",   "period": "30d",  "weight": 1},
]

# ── スーパートレンドパラメータ ────────────────────────────
SUPERTREND_PARAMS = {
    "atr_period": 10,    # ATR計算期間
    "multiplier": 3.0,   # バンド幅の倍率
}

# ── ダウ理論パラメータ ────────────────────────────────────
DOW_PARAMS = {
    "window":     5,   # スイングポイント検出のウィンドウ（前後N本）
    "min_swings": 4,   # 判定に必要な最低スイング数
}

# ── ピックアップ条件 ──────────────────────────────────────
# 全タイムフレームのスコアが閾値以上 → アラート候補として抽出
PICKUP_CONDITIONS = {
    # MTFスコアが高いもの（方向一致度）
    "mtf_score_threshold": 70,      # 0〜100点。この点数以上をピックアップ

    # ダウ理論でトレンド確認済み
    "require_dow_trend": True,       # True: 上昇 or 下降トレンド確定のみ

    # スーパートレンドの向き（日足）
    "require_supertrend_align": True, # True: 日足STとダウ理論の向きが一致

    # ピックアップ時の最低タイムフレーム一致数（4TFのうちN個以上）
    "min_tf_agreement": 3,
}

# ── 出力設定 ──────────────────────────────────────────────
OUTPUT = {
    "html_path": "output/report.html",
    "title": "マーケット分析レポート",
    "auto_refresh_minutes": 15,      # HTMLの自動リフレッシュ間隔（0で無効）
}
