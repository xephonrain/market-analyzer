#!/usr/bin/env python3
# ============================================================
#  analyze.py  - メイン分析スクリプト
# ============================================================
import sys, os, warnings
from datetime import datetime
import yfinance as yf
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config
from config import OUTPUT
from indicators.supertrend import calculate_supertrend, get_supertrend_summary
from indicators.dow_theory  import analyze_dow_theory, detect_swing_points

warnings.filterwarnings("ignore")


def fetch_data(ticker, interval, period):
    try:
        # yfinance 1.4.x 対応: Ticker().history() を使用
        t = yf.Ticker(ticker)
        df = t.history(interval=interval, period=period, auto_adjust=True)
        if df is None or len(df) < 10:
            # fallback: download() with multi_level_index=False
            df = yf.download(ticker, interval=interval, period=period,
                             progress=False, auto_adjust=True,
                             multi_level_index=False)
        if df is None or len(df) < 10:
            print(f"  [WARNING] {ticker} ({interval}): データ不足 ({len(df) if df is not None else 0}本)")
            return None
        # MultiIndex列のフラット化
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # 必要な列が揃っているか確認
        required = ['Open', 'High', 'Low', 'Close']
        missing = [c for c in required if c not in df.columns]
        if missing:
            print(f"  [WARNING] {ticker}: 列不足 {missing} / 実際の列: {list(df.columns)}")
            return None
        return df.dropna(subset=['Close'])
    except Exception as e:
        print(f"  [ERROR] {ticker} ({interval}): {e}")
        return None


def analyze_one(ticker, interval, period, st_params, dow_params):
    df = fetch_data(ticker, interval, period)
    if df is None:
        return {"error": "データ取得失敗", "st": None, "dow": None, "df": None}
    try:
        df = calculate_supertrend(df, **st_params)
        df = detect_swing_points(df, dow_params.get("window", 5))
        st  = get_supertrend_summary(df)
        dow = analyze_dow_theory(df, **dow_params)
    except Exception as e:
        print(f"  [ERROR] 分析失敗 {ticker}: {e}")
        return {"error": str(e), "st": None, "dow": None, "df": None}
    return {"st": st, "dow": dow, "df": df}


def calc_mtf_score(tf_results):
    up_score = down_score = total_weight = 0
    agreements = []
    for tf, res in tf_results:
        weight  = tf.get("weight", 1)
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
        agree_count    = sum(1 for d, _ in agreements if d == "up")
    else:
        raw, direction = down_score / total_weight * 100, "down"
        label, color   = f"↓ 下降優勢 ({raw:.0f}pt)", "#ef5350"
        agree_count    = sum(1 for d, _ in agreements if d == "down")

    return {"score": round(raw, 1), "direction": direction, "label": label,
            "color": color, "agree_count": agree_count, "agreements": agreements}


def check_pickup(symbol, mtf_score, tf_results, cond):
    score     = mtf_score.get("score", 0)
    agree     = mtf_score.get("agree_count", 0)
    direction = mtf_score.get("direction", "unknown")

    if score < cond.get("mtf_score_threshold", 70): return None
    if agree < cond.get("min_tf_agreement", 3):     return None

    if cond.get("require_dow_trend", True):
        daily = next((r for tf, r in tf_results if tf["label"] in ("Daily", "日足")), None)
        if daily and daily.get("dow", {}).get("trend", "range") not in ("uptrend", "downtrend"):
            return None

    if cond.get("require_supertrend_align", True):
        daily = next((r for tf, r in tf_results if tf["label"] in ("Daily", "日足")), None)
        if daily:
            st_up = daily.get("st", {}).get("direction", 0) == 1
            if st_up != (direction == "up"):
                return None

    daily_res   = next((r for tf, r in tf_results if tf["label"] in ("Daily", "日足")), None)
    elapsed_str = None
    bars_since  = None
    if daily_res and daily_res.get("dow"):
        elapsed_str = daily_res["dow"].get("elapsed_str")
        bars_since  = daily_res["dow"].get("bars_since")

    return {"name": symbol["name"], "ticker": symbol["ticker"],
            "category": symbol["category"], "direction": direction,
            "score": score, "label": mtf_score["label"],
            "color": mtf_score["color"], "agree": agree,
            "elapsed_str": elapsed_str, "bars_since": bars_since}


def main():
    print(f"\n{'='*55}")
    print(f"  マーケット分析  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}")

    # config読み込み
    cfg               = load_config()
    symbols_all       = cfg.get("symbols", [])
    timeframes_all    = cfg.get("timeframes", [])
    st_params         = cfg.get("supertrend_params", {"atr_period": 10, "multiplier": 3.0})
    dow_params        = cfg.get("dow_params", {"window": 5, "min_swings": 4})
    pickup_cond       = cfg.get("pickup_conditions", {})

    enabled_symbols   = [s for s in symbols_all    if s.get("enabled", True)]
    enabled_timeframes= [tf for tf in timeframes_all if tf.get("enabled", True)]

    print(f"  銘柄: {len(enabled_symbols)}件 / TF: {len(enabled_timeframes)}本")
    print(f"  ST params: {st_params}")
    print(f"  Dow params: {dow_params}")

    from chart  import build_chart
    from report import generate_html

    all_results    = []
    pickup_list    = []
    chart_html_map = {}

    for sym in enabled_symbols:
        print(f"\n▶ {sym['name']} ({sym['ticker']})")
        tf_results = []
        sid = sym["ticker"].replace("=","").replace("^","").replace(".","")

        for tf in enabled_timeframes:
            print(f"  [{tf['label']}] ", end="", flush=True)
            res = analyze_one(sym["ticker"], tf["interval"], tf["period"],
                              st_params, dow_params)
            df = res.pop("df", None)
            tf_results.append((tf, res))

            st_label  = res["st"]["label"]  if res.get("st")  else "N/A"
            dow_label = res["dow"]["label"] if res.get("dow") else "N/A"
            print(f"ST:{st_label}  Dow:{dow_label}")

            if df is not None and res.get("st") and res.get("dow"):
                tid = f"{sid}_{tf['label']}"
                chart_html_map[tid] = build_chart(
                    df, sym["name"], tf["label"], res["st"], res["dow"])
            else:
                print(f"  [WARNING] チャート生成スキップ: df={df is not None} st={res.get('st') is not None} dow={res.get('dow') is not None}")

        mtf    = calc_mtf_score(tf_results)
        pickup = check_pickup(sym, mtf, tf_results, cond=pickup_cond)
        if pickup:
            pickup_list.append(pickup)
            print(f"  ★ ピックアップ ({mtf['label']})")

        all_results.append({"symbol": sym, "tf_results": tf_results, "mtf_score": mtf})

    # ホット銘柄
    print(f"\n  ホット銘柄取得中...")
    hot_list = []
    try:
        from hot_stocks import fetch_hot_stocks
        hot_list = fetch_hot_stocks()
    except Exception as e:
        print(f"  [WARNING] ホット銘柄取得失敗: {e}")

    # ピックアップ銘柄の追加情報取得
    symbol_info_map = {}
    if pickup_list:
        print(f"\n  ピックアップ銘柄の詳細情報取得中...")
        try:
            from symbol_info import fetch_all_symbol_info
            tickers = [p["ticker"] for p in pickup_list]
            symbol_info_map = fetch_all_symbol_info(tickers)
        except Exception as e:
            print(f"  [WARNING] 詳細情報取得失敗: {e}")

    # HTML生成
    print(f"\n{'='*55}")
    print("  HTMLレポート生成中...")
    html = generate_html(all_results, pickup_list, chart_html_map,
                         hot_list=hot_list, symbol_info_map=symbol_info_map)

    out_path = OUTPUT.get("html_path", "output/report.html")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = len(html) // 1024
    print(f"  → {out_path} ({size_kb} KB)")
    print(f"\n★ ピックアップ: {len(pickup_list)}件")
    for p in pickup_list:
        print(f"   {p['name']} ({p['ticker']}) : {p['label']}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()

