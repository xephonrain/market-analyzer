#!/usr/bin/env python3
# ============================================================
#  scanner.py  - 出来高上位銘柄スキャン
# ============================================================
import yfinance as yf
import pandas as pd
import warnings
import time
warnings.filterwarnings("ignore")

from indicators.supertrend import calculate_supertrend, get_supertrend_summary
from indicators.dow_theory  import analyze_dow_theory, detect_swing_points
from config import SUPERTREND_PARAMS, DOW_PARAMS


# ── スキャン用TF設定（3TF） ───────────────────────────────
SCAN_TFS = [
    {"label": "Daily", "interval": "1d", "period": "1y",  "weight": 3},
    {"label": "4H",    "interval": "1h", "period": "60d", "weight": 2},
    {"label": "1H",    "interval": "1h", "period": "30d", "weight": 1},
]


def get_jp_candidates(max_price: float = 1000, top_n: int = 100) -> list:
    """日本株の出来高上位銘柄を取得してフィルタ"""
    try:
        # Yahoo Finance スクリーナーから取得
        screener_tickers = []

        # yfinanceのscreenerを使用
        import urllib.request, json
        url = ("https://query2.finance.yahoo.com/v1/finance/screener?"
               "formatted=true&lang=ja-JP&region=JP&"
               "crumb=&count=100&scrIds=most_actives_jp")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            quotes = (data.get("finance", {})
                         .get("result", [{}])[0]
                         .get("quotes", []))
            for q in quotes:
                ticker = q.get("symbol", "")
                price  = q.get("regularMarketPrice", {}).get("raw", 9999)
                if ticker and price <= max_price:
                    screener_tickers.append({
                        "ticker": ticker,
                        "name":   q.get("shortName", ticker.replace(".T","")),
                        "price":  price,
                        "volume": q.get("regularMarketVolume", {}).get("raw", 0),
                        "category": "JP Stocks",
                    })
        except Exception as e:
            print(f"  [WARNING] JP screener: {e}")

        # フォールバック：日経225の主要銘柄から低価格株を取得
        if len(screener_tickers) < 10:
            fallback_tickers = [
                "8306.T","8316.T","8411.T","8591.T","9432.T","9433.T",
                "9984.T","7203.T","6758.T","6501.T","6367.T","4661.T",
                "9020.T","2802.T","4502.T","5401.T","8001.T","8031.T",
                "3382.T","2914.T","6902.T","6954.T","4063.T","6981.T",
            ]
            infos = yf.download(
                fallback_tickers, period="2d", interval="1d",
                group_by="ticker", auto_adjust=True, progress=False
            )
            for tk in fallback_tickers:
                try:
                    if tk in infos.columns.get_level_values(0):
                        close = float(infos[tk]["Close"].dropna().iloc[-1])
                    else:
                        close = float(infos["Close"].dropna().iloc[-1])
                    if close <= max_price:
                        screener_tickers.append({
                            "ticker": tk,
                            "name":   tk.replace(".T",""),
                            "price":  close,
                            "volume": 0,
                            "category": "JP Stocks",
                        })
                except Exception:
                    pass

        print(f"  JP候補: {len(screener_tickers)}件 (≤¥{max_price})")
        return screener_tickers[:top_n]

    except Exception as e:
        print(f"  [ERROR] JP candidates: {e}")
        return []


def get_us_candidates(max_price: float = 50, top_n: int = 100) -> list:
    """US株の出来高上位銘柄を取得してフィルタ"""
    try:
        import urllib.request, json
        url = ("https://query2.finance.yahoo.com/v1/finance/screener?"
               "formatted=true&lang=en-US&region=US&"
               "crumb=&count=100&scrIds=most_actives")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        candidates = []
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            quotes = (data.get("finance", {})
                         .get("result", [{}])[0]
                         .get("quotes", []))
            for q in quotes:
                ticker = q.get("symbol", "")
                price  = q.get("regularMarketPrice", {}).get("raw", 9999)
                if ticker and price <= max_price:
                    candidates.append({
                        "ticker": ticker,
                        "name":   q.get("shortName", ticker),
                        "price":  price,
                        "volume": q.get("regularMarketVolume", {}).get("raw", 0),
                        "category": "US Stocks",
                    })
        except Exception as e:
            print(f"  [WARNING] US screener: {e}")

        print(f"  US候補: {len(candidates)}件 (≤${max_price})")
        return candidates[:top_n]
    except Exception as e:
        print(f"  [ERROR] US candidates: {e}")
        return []


def _fetch_df(ticker: str, interval: str, period: str) -> pd.DataFrame:
    """データ取得"""
    try:
        t = yf.Ticker(ticker)
        df = t.history(interval=interval, period=period)
        if df.empty or len(df) < 20:
            return None
        return df
    except Exception:
        return None


def _analyze_tf(df: pd.DataFrame) -> dict:
    """単一TFの分析"""
    if df is None or len(df) < 20:
        return {"st": None, "dow": None}
    df = calculate_supertrend(df, **SUPERTREND_PARAMS)
    df = detect_swing_points(df, DOW_PARAMS["window"])
    st  = get_supertrend_summary(df)
    dow = analyze_dow_theory(df, **DOW_PARAMS)
    return {"st": st, "dow": dow}


def _is_1h_fresh_reversal(res_1h: dict, max_bars: int = 20) -> tuple:
    """1Hが転換直後かどうかチェック。(is_fresh, direction, bars_since)"""
    st  = res_1h.get("st")  or {}
    dow = res_1h.get("dow") or {}
    if not st or st.get("label") == "N/A":
        return False, None, None

    # STの方向
    st_dir = st.get("direction", 0)
    if st_dir == 0:
        return False, None, None

    # 転換からの経過本数
    bars = dow.get("bars_since")
    if bars is None:
        # STのbars_since_changeを使う
        bars = st.get("bars_since_change", 999)

    direction = "up" if st_dir == 1 else "down"
    is_fresh  = (bars is not None and bars <= max_bars)
    return is_fresh, direction, bars


def scan_symbol(sym_info: dict, max_1h_bars: int = 20) -> dict | None:
    """
    1銘柄をスキャン。チャンスゾーンなら結果を返す、そうでなければNone。

    チャンスゾーン条件:
    - 1Hが転換直後（max_1h_bars本以内）
    - 日足と4HがST方向一致（1Hと同方向）
    """
    ticker = sym_info["ticker"]
    results = {}

    for tf in SCAN_TFS:
        df = _fetch_df(ticker, tf["interval"], tf["period"])
        results[tf["label"]] = _analyze_tf(df)

    # 1H転換チェック
    is_fresh, direction, bars = _is_1h_fresh_reversal(
        results.get("1H", {}), max_bars=max_1h_bars)
    if not is_fresh:
        return None

    # 日足・4HのST方向チェック
    daily_st = (results.get("Daily", {}).get("st") or {}).get("direction", 0)
    h4_st    = (results.get("4H",    {}).get("st") or {}).get("direction", 0)

    expected = 1 if direction == "up" else -1
    daily_ok = (daily_st == expected)
    h4_ok    = (h4_st    == expected)

    if not (daily_ok or h4_ok):
        return None

    # スコア計算（3TF）
    score = 0
    total = 0
    for tf in SCAN_TFS:
        w  = tf["weight"]
        st = (results.get(tf["label"], {}).get("st") or {})
        if st.get("direction", 0) == expected:
            score += w
        total += w
    score_pct = round(score / total * 100) if total > 0 else 0

    # 価格位置
    daily_dow = results.get("Daily", {}).get("dow") or {}
    highs = daily_dow.get("swing_highs", [])
    lows  = daily_dow.get("swing_lows",  [])
    range_pos = None
    if highs and lows:
        h = highs[-1][1]
        l = lows[-1][1]
        p = sym_info["price"]
        if h > l:
            range_pos = round((p - l) / (h - l) * 100)

    return {
        "ticker":     ticker,
        "name":       sym_info["name"],
        "category":   sym_info["category"],
        "price":      sym_info["price"],
        "direction":  direction,
        "score":      score_pct,
        "bars_since": bars,
        "daily_ok":   daily_ok,
        "h4_ok":      h4_ok,
        "range_pos":  range_pos,
        "tf_results": [(tf, results[tf["label"]]) for tf in
                       [t["label"] for t in SCAN_TFS]],
    }


def run_scan(jp_max_price: float = 1000, us_max_price: float = 50,
             max_1h_bars: int = 20, max_results: int = 20) -> list:
    """
    メインスキャン関数。
    Returns: チャンスゾーン銘柄のリスト（スコア降順）
    """
    print("\n  スキャン開始...")

    jp_candidates = get_jp_candidates(jp_max_price)
    us_candidates = get_us_candidates(us_max_price)
    all_candidates = jp_candidates + us_candidates

    print(f"  スキャン対象: {len(all_candidates)}件")

    results = []
    for i, sym in enumerate(all_candidates):
        try:
            r = scan_symbol(sym, max_1h_bars=max_1h_bars)
            if r:
                results.append(r)
                print(f"  ✓ {sym['ticker']} {r['direction']} {r['score']}pt "
                      f"1H転換{r['bars_since']}本前")
        except Exception as e:
            pass
        # レート制限対策
        if i % 10 == 9:
            time.sleep(1)

    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:max_results]
    print(f"  スキャン完了: {len(results)}件ヒット")
    return results
