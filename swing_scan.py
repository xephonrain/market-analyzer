#!/usr/bin/env python3
# ============================================================
#  swing_scan.py - 日本株 現物・短期スイング(数日〜1週間) 買い候補スクリーナー
#
#  流れ
#   1) JPX上場銘柄一覧 → 2) 直近1か月で株価/ボラ/売買代金を粗く絞る
#   3) 残りの2年分で 週足+日足 の ダウ理論 + スーパートレンド を判定
#   4) 余力(SWING_CAPITAL)・許容損失(SWING_MAX_LOSS)に収まる銘柄だけ残す
#   5) 押し目指値/成行のエントリー候補・損切り・直近高値までのRRを計算
#
#  注意
#   - 公開リポジトリのため、金額は環境変数で受け取り、出力JSONにも書かない
#   - 買い(現物)のみ。決算・ニュースの確認は別工程（AI）で行う前提
# ============================================================
import io
import json
import math
import os
import sys
import time
import urllib.request
import warnings
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from indicators.dow_theory import analyze_dow_theory, detect_swing_points  # noqa: E402
from indicators.supertrend import (calculate_atr, calculate_supertrend,   # noqa: E402
                                   get_supertrend_summary)

JST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0"}


# ── 設定 ─────────────────────────────────────────────────
def load_cfg(path=None, env=None):
    env = os.environ if env is None else env
    with open(path or os.path.join(BASE, "swing_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    try:
        cfg["capital"] = float(env["SWING_CAPITAL"])
        cfg["max_loss"] = float(env["SWING_MAX_LOSS"])
    except (KeyError, ValueError):
        raise SystemExit("環境変数 SWING_CAPITAL / SWING_MAX_LOSS が未設定です（円の数値）")
    return cfg


# ── 銘柄一覧 ─────────────────────────────────────────────
def load_universe(cfg):
    cache = os.path.join(BASE, cfg["universe_cache"])
    uni = None
    try:
        req = urllib.request.Request(cfg["universe_url"], headers=UA)
        raw = urllib.request.urlopen(req, timeout=60).read()
        df = pd.read_excel(io.BytesIO(raw), dtype=str)
        code = next(c for c in df.columns if str(c).strip() == "コード")
        name = next(c for c in df.columns if "銘柄名" in str(c))
        mkt = next(c for c in df.columns if "市場" in str(c))
        uni = pd.DataFrame({"code": df[code].str.strip(), "name": df[name], "market": df[mkt]})
        uni.to_csv(cache, index=False, encoding="utf-8-sig")
        print(f"  [universe] JPXから取得 {len(uni)}件")
    except Exception as e:
        print(f"  [universe] 取得失敗: {e}")
        if os.path.exists(cache):
            uni = pd.read_csv(cache, dtype=str)
            print(f"  [universe] キャッシュを使用 {len(uni)}件")
    if uni is None:
        return None
    ok = uni["market"].fillna("").apply(lambda m: any(a in m for a in cfg["markets"]))
    uni = uni[ok & uni["code"].notna()].copy()
    uni["ticker"] = uni["code"] + ".T"
    return uni.reset_index(drop=True)


# ── データ取得 ───────────────────────────────────────────
def download_daily(tickers, period, chunk=150, pause=1.0):
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        try:
            data = yf.download(part, period=period, interval="1d", group_by="ticker",
                               auto_adjust=True, progress=False, threads=True)
        except Exception as e:
            print(f"  [download] chunk{i} 失敗: {e}")
            continue
        for t in part:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if t not in data.columns.get_level_values(0):
                        continue
                    d = data[t]
                else:
                    d = data
                d = d.dropna(subset=["Close"])
                if len(d) >= 5:
                    out[t] = d[["Open", "High", "Low", "Close", "Volume"]]
            except Exception:
                continue
        time.sleep(pause)
    return out


# ── 指標 ─────────────────────────────────────────────────
def basic_metrics(df, atr_period):
    atr = calculate_atr(df, atr_period)
    c = float(df["Close"].iloc[-1])
    a = float(atr.iloc[-1])
    turnover = float((df["Close"] * df["Volume"]).iloc[-20:].mean())
    vavg = float(df["Volume"].iloc[-21:-1].mean()) if len(df) > 5 else 0.0
    vol_ratio = float(df["Volume"].iloc[-1]) / vavg if vavg > 0 else None
    return {"close": c, "atr": a, "atr_pct": a / c * 100 if c > 0 else 0.0,
            "turnover20": turnover, "vol_ratio": vol_ratio}


def to_weekly(df):
    return (df.resample("W-FRI")
              .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
              .dropna(subset=["Close"]))


def _tf(df, cfg, window):
    d = calculate_supertrend(df, atr_period=cfg["st_atr"], multiplier=cfg["st_mult"])
    return d, get_supertrend_summary(d), analyze_dow_theory(d, window=window, min_swings=4, dedupe_ties=True)


def _bars_since_buy(d):
    idx = np.flatnonzero((d["st_signal"] == "BUY").values)
    return int(len(d) - 1 - idx[-1]) if len(idx) else None


def size_position(entry, stop, cfg):
    """100株単位。資金と許容損失の両方に収まる最大株数。収まらなければNone"""
    risk = entry - stop
    if risk <= 0 or entry <= 0:
        return None
    lot = cfg["lot"]
    n = math.floor(min(cfg["capital"] / entry, cfg["max_loss"] / risk) / lot) * lot
    if n < lot:
        return None
    return int(n)


def evaluate(df, cfg):
    """1銘柄を判定。戻り値: (候補dict or None, 除外理由)"""
    m = basic_metrics(df, cfg["atr_period"])
    if m["close"] > cfg["capital"] / cfg["lot"]:
        return None, "too_expensive"
    if m["close"] < cfg["min_price"]:
        return None, "too_cheap"
    if m["atr_pct"] < cfg["min_atr_pct"]:
        return None, "low_vol"
    if m["turnover20"] < cfg["min_turnover_jpy"]:
        return None, "low_turnover"

    w = to_weekly(df)
    if len(w) < 30 or len(df) < 60:
        return None, "short_history"
    dd, st_d, dow_d = _tf(df, cfg, cfg["swing_window_daily"])
    _, st_w, dow_w = _tf(w, cfg, cfg["swing_window_weekly"])

    ind = {"W_dow": dow_w["trend"] == "uptrend", "W_st": st_w["direction"] == 1,
           "D_dow": dow_d["trend"] == "uptrend", "D_st": st_d["direction"] == 1}
    agree = sum(ind.values())
    bars_buy = _bars_since_buy(dd)

    if ind["D_dow"] and ind["D_st"] and ind["W_st"]:
        kind = "trend"      # 週足環境が上向き + 日足の押し目
    elif (ind["D_st"] and bars_buy is not None and bars_buy <= cfg["turn_max_bars"]
          and dow_w["trend"] != "downtrend" and dow_d["trend"] != "downtrend"):
        kind = "turn"       # 日足STが上転換した直後
    else:
        return None, "no_signal"

    # 水準: 直近の確定スイング安値(ダウ崩れライン) とその後の最高値
    sw = detect_swing_points(df, cfg["swing_window_daily"], dedupe_ties=True)
    lows = sw[sw["swing_low"]]
    if lows.empty:
        return None, "no_swing"
    sl_date, sl_val = lows.index[-1], float(lows["Low"].iloc[-1])
    last_high = float(df.loc[sl_date:, "High"].max())
    if m["close"] <= sl_val:
        return None, "below_swing_low"

    stop = math.floor(sl_val - cfg["stop_buffer_atr"] * m["atr"])
    entries = {"market": int(round(m["close"]))}
    pb = math.floor(last_high - cfg["pullback_ratio"] * (last_high - sl_val))
    if stop < pb < m["close"]:
        entries["pullback"] = pb

    chosen = None
    reasons = []
    for name in ("pullback", "market"):         # 押し目指値を優先
        if name not in entries:
            continue
        e = entries[name]
        n = size_position(e, stop, cfg)
        if n is None:
            reasons.append("risk_too_wide")
            continue
        rr = (last_high - e) / (e - stop)
        if rr < cfg["min_rr"]:
            reasons.append("rr_low")
            continue
        chosen = (name, e, n, rr)
        break
    if chosen is None:
        return None, reasons[0] if reasons else "no_entry"

    name, e, n, rr = chosen
    return {
        "kind": kind, "agree": agree, "ind": {k: bool(v) for k, v in ind.items()},
        "close": round(m["close"], 1), "atr_pct": round(m["atr_pct"], 2),
        "turnover20_oku": round(m["turnover20"] / 1e8, 2),
        "vol_ratio": round(m["vol_ratio"], 2) if m["vol_ratio"] else None,
        "bars_since_st_buy": bars_buy,
        "swing_low": round(sl_val, 1), "recent_high": round(last_high, 1),
        "entry_type": name, "entry": e, "entries_available": entries,
        "stop": stop, "rr_to_recent_high": round(rr, 2),
        # 金額は書かない（公開リポジトリ）。100株あたりの値のみ
        "risk_per_100": round((e - stop) * 100), "cost_per_100": round(e * 100),
        "earnings_check": "未確認（AI工程で決算日・開示を確認）",
    }, "ok"


# ── 全体 ─────────────────────────────────────────────────
def run(cfg, fetch=download_daily, universe=None, now=None):
    now = now or datetime.now(JST)
    uni = universe if universe is not None else load_universe(cfg)
    if uni is None or uni.empty:
        raise SystemExit("銘柄一覧を取得できませんでした（キャッシュもなし）")
    names = dict(zip(uni["ticker"], uni["name"]))
    mkts = dict(zip(uni["ticker"], uni["market"]))
    tickers = list(uni["ticker"])
    print(f"  対象銘柄: {len(tickers)}")

    # 1段目: 直近1か月で粗く絞る（ボラは短い窓なので閾値を緩める）
    d1 = fetch(tickers, "1mo", cfg["download_chunk"], cfg["download_pause"])
    max_price = cfg["capital"] / cfg["lot"]
    s1 = []
    for t, df in d1.items():
        if len(df) < 15:
            continue
        mt = basic_metrics(df, min(cfg["atr_period"], len(df) - 1))
        if not (cfg["min_price"] <= mt["close"] <= max_price):
            continue
        if mt["atr_pct"] < cfg["min_atr_pct"] * 0.8 or mt["turnover20"] < cfg["min_turnover_jpy"]:
            continue
        s1.append(t)
    print(f"  1段目通過: {len(s1)} / 取得 {len(d1)}")

    # 2段目: 2年分で週足・日足を判定
    d2 = fetch(s1, "2y", cfg["download_chunk"], cfg["download_pause"])
    as_of = max((df.index[-1] for df in d2.values()), default=None)
    counts, cands = {}, []
    for t, df in d2.items():
        if as_of is not None and (as_of - df.index[-1]).days > cfg["stale_days"]:
            counts["stale"] = counts.get("stale", 0) + 1
            continue
        try:
            r, why = evaluate(df, cfg)
        except Exception as e:
            r, why = None, f"error:{type(e).__name__}"
        counts[why] = counts.get(why, 0) + 1
        if r:
            r.update({"ticker": t, "name": names.get(t, t), "market": mkts.get(t, "")})
            cands.append(r)

    cands.sort(key=lambda x: (-x["agree"], -min(x["vol_ratio"] or 0, 5), -x["rr_to_recent_high"]))
    out = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M JST"),
        "as_of": as_of.strftime("%Y-%m-%d") if as_of is not None else None,
        "method": ("週足+日足のダウ理論とスーパートレンド。買いのみ。損切り=直近確定スイング安値-0.2ATR、"
                   "押し目指値=直近レッグの50%戻し、RR=直近高値まで。数値は機械判定で、決算・ニュースは未確認"),
        "funnel": {"universe": len(tickers), "stage1": len(s1), "evaluated": len(d2),
                   "candidates": len(cands), "excluded": counts},
        "top": cands[:cfg["top_n"]],
        "candidates": cands[:cfg["list_n"]],
    }
    return out


def write_outputs(out, cfg):
    p = os.path.join(BASE, cfg["out_json"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    # 後日の採点用ログ（TOP N を毎日追記）
    lp = os.path.join(BASE, cfg["out_log"])
    rows = [{"as_of": out["as_of"], "rank": i + 1, "ticker": c["ticker"], "name": c["name"],
             "kind": c["kind"], "agree": c["agree"], "close": c["close"], "entry_type": c["entry_type"],
             "entry": c["entry"], "stop": c["stop"], "recent_high": c["recent_high"],
             "rr": c["rr_to_recent_high"], "vol_ratio": c["vol_ratio"]}
            for i, c in enumerate(out["top"])]
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(lp, mode="a", header=not os.path.exists(lp), index=False, encoding="utf-8-sig")
    print(f"  → {cfg['out_json']} / TOP{len(out['top'])}件")


if __name__ == "__main__":
    cfg = load_cfg()
    result = run(cfg)
    write_outputs(result, cfg)
    print(json.dumps(result["funnel"], ensure_ascii=False))
