#!/usr/bin/env python3
# ============================================================
#  analyze.py  - メイン分析スクリプト (Phase 2: チャート込み)
#  実行: python analyze.py
# ============================================================
import sys, os, warnings
from datetime import datetime

import yfinance as yf
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from config_loader import load_config
from config import OUTPUT
from indicators.supertrend import calculate_supertrend, get_supertrend_summary
from indicators.dow_theory  import analyze_dow_theory, detect_swing_points

warnings.filterwarnings("ignore")


def fetch_data(ticker, interval, period):
    try:
        df = yf.download(ticker, interval=interval, period=period,
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 20:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception as e:
        print(f"  [ERROR] {ticker} ({interval}): {e}")
        return None


def analyze_one(ticker, interval, period):
    df = fetch_data(ticker, interval, period)
    if df is None:
        return {"error": "データ取得失敗", "st": None, "dow": None, "df": None}
    try:
        df = calculate_supertrend(df, **SUPERTREND_PARAMS_)
        df = detect_swing_points(df, DOW_PARAMS_.get("window",5))
        st  = get_supertrend_summary(df)
        dow = analyze_dow_theory(df, **DOW_PARAMS)
    except Exception as e:
        return {"error": str(e), "st": None, "dow": None, "df": None}
    return {"st": st, "dow": dow, "df": df}


def calc_mtf_score(tf_results):
    up_score = down_score = total_weight = 0
    agreements = []
    for tf, res in tf_results:
        weight  = tf["weight"]
        st  = res.get("st")  or {}
        dow = res.get("dow") or {}
        st_dir  = st.get("direction", 0)
        dow_dir = dow.get("trend", "range")
        if st_dir == 1 and dow_dir == "uptrend":
            up_score   += weight
            agreements.append(("up", tf["label"]))
        elif st_dir == -1 and dow_dir == "downtrend":
            down_score += weight
            agreements.append(("down", tf["label"]))
        total_weight += weight

    if total_weight == 0:
        return {"score": 0, "direction": "unknown", "label": "判定不能",
                "color": "#888", "agree_count": 0, "agreements": []}

    if up_score >= down_score:
        raw, direction = up_score / total_weight * 100, "up"
        label, color   = f"↑ 上昇優勢 ({raw:.0f}pt)", "#26a69a"
        agree_count    = sum(1 for d,_ in agreements if d == "up")
    else:
        raw, direction = down_score / total_weight * 100, "down"
        label, color   = f"↓ 下降優勢 ({raw:.0f}pt)", "#ef5350"
        agree_count    = sum(1 for d,_ in agreements if d == "down")

    return {"score": round(raw,1), "direction": direction, "label": label,
            "color": color, "agree_count": agree_count, "agreements": agreements}


def check_pickup(symbol, mtf_score, tf_results, cond=None):
    if cond is None:
        from config import PICKUP_CONDITIONS
        cond = PICKUP_CONDITIONS
    score = mtf_score.get("score", 0)
    agree = mtf_score.get("agree_count", 0)
    direction = mtf_score.get("direction", "unknown")

    if score < cond["mtf_score_threshold"]:  return None
    if agree < cond["min_tf_agreement"]:      return None

    if cond["require_dow_trend"]:
        daily = next((r for tf,r in tf_results if tf["label"]=="日足"), None)
        if daily and daily.get("dow",{}).get("trend","range") not in ("uptrend","downtrend"):
            return None

    if cond["require_supertrend_align"]:
        daily = next((r for tf,r in tf_results if tf["label"]=="日足"), None)
        if daily:
            st_up  = daily.get("st",{}).get("direction",0) == 1
            if st_up != (direction == "up"):
                return None

    return {"name": symbol["name"], "ticker": symbol["ticker"],
            "category": symbol["category"], "direction": direction,
            "score": score, "label": mtf_score["label"],
            "color": mtf_score["color"], "agree": agree}


def main():
    print(f"\n{'='*55}")
    print(f"  マーケット分析  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}")

    from chart  import build_chart
    from report import generate_html

    _cfg = load_config()
    SYMBOLS_    = _cfg.get("symbols", [])
    TIMEFRAMES_ = [tf for tf in _cfg.get("timeframes", []) if tf.get("enabled", True)]
    SUPERTREND_PARAMS_ = _cfg.get("supertrend_params", {"atr_period":10,"multiplier":3.0})
    DOW_PARAMS_        = _cfg.get("dow_params", {"window":5,"min_swings":4})
    PICKUP_CONDITIONS_ = _cfg.get("pickup_conditions", {})

    enabled = [s for s in SYMBOLS_ if s.get("enabled", True)]
    all_results    = []
    pickup_list    = []
    chart_html_map = {}

    for sym in enabled:
        print(f"\n▶ {sym['name']} ({sym['ticker']})")
        tf_results = []
        sid = sym["ticker"].replace("=","").replace("^","").replace(".","")

        for tf in TIMEFRAMES_:
            print(f"  [{tf['label']}] ", end="", flush=True)
            res = analyze_one(sym["ticker"], tf["interval"], tf["period"])
            # df を取り出してチャートを生成
            df  = res.pop("df", None)
            tf_results.append((tf, res))

            st_label  = res["st"]["label"] if res.get("st")  else "N/A"
            dow_label = res["dow"]["label"] if res.get("dow") else "N/A"
            print(f"ST:{st_label}  Dow:{dow_label}")

            if df is not None and res.get("st") and res.get("dow"):
                tid = f"{sid}_{tf['label']}"
                chart_html_map[tid] = build_chart(
                    df, sym["name"], tf["label"], res["st"], res["dow"])

        mtf    = calc_mtf_score(tf_results)
        pickup = check_pickup(sym, mtf, tf_results, cond=PICKUP_CONDITIONS_)
        if pickup:
            pickup_list.append(pickup)
            print(f"  ★ ピックアップ対象！ ({mtf['label']})")

        all_results.append({"symbol": sym, "tf_results": tf_results, "mtf_score": mtf})

    print(f"\n{'='*55}")
    print("  HTMLレポート生成中...")
    # ── ホット銘柄取得 ──────────────────────────────────
    print("\n  ホット銘柄取得中...")
    hot_list = []
    try:
        from hot_stocks import fetch_hot_stocks
        hot_list = fetch_hot_stocks()
    except Exception as e:
        print(f"  [WARNING] ホット銘柄取得失敗: {e}")

    html = generate_html(all_results, pickup_list, chart_html_map, hot_list=hot_list)
    os.makedirs(os.path.dirname(OUTPUT["html_path"]), exist_ok=True)
    with open(OUTPUT["html_path"], "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = len(html) / 1024
    print(f"  → {OUTPUT['html_path']} ({size_kb:.0f} KB)")
    print(f"\n★ ピックアップ: {len(pickup_list)}件")
    for p in pickup_list:
        print(f"   {p['name']} ({p['ticker']}) : {p['label']}")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
