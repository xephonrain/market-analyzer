#!/usr/bin/env python3
# ============================================================
#  entry_logic.py  - エントリーポイント分析
#  A) トレンドフォロー型
#  B) レンジブレイク待ち型
#  C) 転換直後型
# ============================================================
import pandas as pd
import numpy as np


# ── 星評価 ───────────────────────────────────────────────
def _stars(n):
    return "★" * n + "☆" * (3 - n)


# ── A) トレンドフォロー型 ─────────────────────────────────
def analyze_trend_follow(tf_results: list) -> dict | None:
    """
    上位TFがトレンド確定 + 下位TFでST転換 → エントリー候補

    Returns None if no signal
    """
    # TFを上位から順に確認
    tf_map = {tf["label"]: (tf, res) for tf, res in tf_results}

    # 上位TF（週足・日足）のトレンド確認
    upper_labels = ["Weekly", "Daily", "週足", "日足"]
    lower_labels  = ["4H", "1H", "15M", "4時間", "1時間", "15分"]

    upper_trends = []
    for label in upper_labels:
        if label in tf_map:
            tf, res = tf_map[label]
            dow = res.get("dow", {})
            st  = res.get("st", {})
            if dow.get("trend") in ("uptrend", "downtrend"):
                upper_trends.append({
                    "label": label,
                    "trend": dow["trend"],
                    "st_dir": st.get("direction", 0),
                    "dow_label": dow.get("label", ""),
                    "st_label":  st.get("label", ""),
                })

    if not upper_trends:
        return None

    # 上位TFの方向が一致しているか
    directions = [t["trend"] for t in upper_trends]
    if len(set(directions)) > 1:
        return None  # 上位TF間で不一致

    direction = directions[0]
    agree_count = len(upper_trends)

    # 下位TFでSTシグナル（BUY/SELL）があるか
    entry_signal = None
    entry_tf = None
    for label in lower_labels:
        if label in tf_map:
            tf, res = tf_map[label]
            st = res.get("st", {})
            sig = st.get("signal")
            if sig == "BUY" and direction == "uptrend":
                entry_signal = "BUY"
                entry_tf = label
                break
            elif sig == "SELL" and direction == "downtrend":
                entry_signal = "SELL"
                entry_tf = label
                break

    # 強さ算出
    strength = min(agree_count, 3)
    if not entry_signal:
        strength = max(strength - 1, 1)

    # 価格計算（日足のST値をエントリー基準に）
    entry_price = None
    sl_price    = None
    tp_price    = None

    daily_key = next((l for l in ["Daily", "日足"] if l in tf_map), None)
    if daily_key:
        tf, res = tf_map[daily_key]
        st  = res.get("st", {})
        dow = res.get("dow", {})
        st_val = st.get("value")
        close  = st.get("close")

        if direction == "uptrend":
            entry_price = st_val  # STライン（サポート）付近
            # SL: 直近スイング安値
            lows = dow.get("swing_lows", [])
            sl_price = lows[-2][1] if len(lows) >= 2 else None
            # TP: 直近スイング高値
            highs = dow.get("swing_highs", [])
            tp_price = highs[-1][1] if highs else None
        else:
            entry_price = st_val  # STライン（レジスタンス）付近
            highs = dow.get("swing_highs", [])
            sl_price = highs[-2][1] if len(highs) >= 2 else None
            lows = dow.get("swing_lows", [])
            tp_price = lows[-1][1] if lows else None

    # RR計算
    rr = None
    if entry_price and sl_price and tp_price:
        risk   = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        if risk > 0:
            rr = round(reward / risk, 1)

    return {
        "type":        "A",
        "type_label":  "TF",
        "direction":   direction,
        "signal":      entry_signal or ("BUY" if direction == "uptrend" else "SELL"),
        "strength":    strength,
        "stars":       _stars(strength),
        "upper_agree": agree_count,
        "entry_tf":    entry_tf,
        "entry_price": round(entry_price, 4) if entry_price else None,
        "sl_price":    round(sl_price,    4) if sl_price    else None,
        "tp_price":    round(tp_price,    4) if tp_price    else None,
        "rr":          rr,
        "desc": (f"上位{agree_count}TF {('上昇' if direction=='uptrend' else '下降')}一致"
                 + (f" / {entry_tf}でST転換" if entry_signal else " / ST転換待ち")),
    }


# ── B) レンジブレイク待ち型 ───────────────────────────────
def analyze_range_break(tf_results: list) -> dict | None:
    """
    上位TFがレンジ + 下位TFでpending or ST収縮 → ブレイク待ち
    """
    tf_map = {tf["label"]: (tf, res) for tf, res in tf_results}

    upper_labels = ["Weekly", "Daily", "週足", "日足"]
    lower_labels  = ["4H", "1H", "15M", "4時間", "1時間", "15分"]

    # 上位TFのレンジ確認
    range_tfs = []
    for label in upper_labels:
        if label in tf_map:
            tf, res = tf_map[label]
            dow = res.get("dow", {})
            if "range" in dow.get("trend", ""):
                range_tfs.append({
                    "label":   label,
                    "trend":   dow.get("trend"),
                    "pending": dow.get("pending", False),
                    "desc":    dow.get("description", ""),
                    "highs":   dow.get("swing_highs", []),
                    "lows":    dow.get("swing_lows", []),
                })

    if not range_tfs:
        return None

    # 下位TFでpendingまたはST方向転換
    lower_signals = []
    for label in lower_labels:
        if label in tf_map:
            tf, res = tf_map[label]
            dow = res.get("dow", {})
            st  = res.get("st", {})
            if dow.get("pending"):
                lower_signals.append({
                    "label":  label,
                    "type":   "pending",
                    "desc":   dow.get("pending_desc", ""),
                    "st_dir": st.get("direction", 0),
                })

    # 強さ算出
    primary = range_tfs[0]  # 最上位TFのレンジ
    has_pending = len(lower_signals) > 0
    is_contracting = "収縮" in primary.get("trend", "")

    if primary["label"] in ("Weekly", "週足"):
        strength = 3
    elif primary["label"] in ("Daily", "日足"):
        strength = 2
    else:
        strength = 1

    if not has_pending and not is_contracting:
        strength = max(strength - 1, 1)

    # ブレイクアウト/ダウン価格
    highs = primary["highs"]
    lows  = primary["lows"]
    breakout_price  = highs[-1][1] if highs else None  # 上抜けターゲット
    breakdown_price = lows[-1][1]  if lows  else None  # 下抜けターゲット

    # 下位TFのST方向でブレイク方向を予測
    predicted_dir = None
    if lower_signals:
        st_dir = lower_signals[0].get("st_dir", 0)
        if st_dir == 1:
            predicted_dir = "UP"
        elif st_dir == -1:
            predicted_dir = "DOWN"

    return {
        "type":           "B",
        "type_label":     "RB",
        "direction":      "range",
        "signal":         "WATCH",
        "strength":       strength,
        "stars":          _stars(strength),
        "range_tf":       primary["label"],
        "predicted_dir":  predicted_dir,
        "breakout_price": round(breakout_price,  4) if breakout_price  else None,
        "breakdown_price":round(breakdown_price, 4) if breakdown_price else None,
        "pending_count":  len(lower_signals),
        "rr":             None,
        "desc": (f"{primary['label']}レンジ"
                 + (f" / {lower_signals[0]['label']}でpending" if lower_signals else "")
                 + (f" / {'上'if predicted_dir=='UP' else '下'}抜け予測" if predicted_dir else "")),
    }


# ── C) 転換直後型 ─────────────────────────────────────────
def analyze_reversal_fresh(tf_results: list) -> dict | None:
    """
    転換直後（bars_since が少ない）のエントリー候補
    """
    tf_map = {tf["label"]: (tf, res) for tf, res in tf_results}

    candidates = []
    for tf, res in tf_results:
        dow = res.get("dow", {})
        st  = res.get("st", {})
        bars = dow.get("bars_since")
        trend = dow.get("trend", "")

        if bars is None or trend not in ("uptrend", "downtrend"):
            continue

        # 強さ: 経過本数で決定
        if bars <= 3:
            strength = 3
        elif bars <= 10:
            strength = 2
        elif bars <= 20:
            strength = 1
        else:
            continue  # 古すぎる

        candidates.append({
            "label":    tf["label"],
            "trend":    trend,
            "bars":     bars,
            "elapsed":  dow.get("elapsed_str", ""),
            "strength": strength,
            "st_val":   st.get("value"),
            "close":    st.get("close"),
            "signal":   st.get("signal"),
            "dow": dow,
        })

    if not candidates:
        return None

    # 最も新しい（bars_sinceが少ない）候補を選択
    best = min(candidates, key=lambda x: x["bars"])

    direction = best["trend"]
    dow = best["dow"]

    # エントリー価格: 転換確定時のSTライン
    entry_price = best["st_val"]

    # SL: 転換確定時のスイング安値/高値
    sl_price = None
    tp_price = None
    if direction == "uptrend":
        lows  = dow.get("swing_lows",  [])
        highs = dow.get("swing_highs", [])
        sl_price = lows[-1][1]  if lows  else None
        tp_price = highs[-1][1] if highs else None
    else:
        highs = dow.get("swing_highs", [])
        lows  = dow.get("swing_lows",  [])
        sl_price = highs[-1][1] if highs else None
        tp_price = lows[-1][1]  if lows  else None

    # RR
    rr = None
    if entry_price and sl_price and tp_price:
        risk   = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        if risk > 0:
            rr = round(reward / risk, 1)

    return {
        "type":        "C",
        "type_label":  "TR",
        "direction":   direction,
        "signal":      "BUY" if direction == "uptrend" else "SELL",
        "strength":    best["strength"],
        "stars":       _stars(best["strength"]),
        "entry_tf":    best["label"],
        "bars_since":  best["bars"],
        "elapsed":     best["elapsed"],
        "entry_price": round(entry_price, 4) if entry_price else None,
        "sl_price":    round(sl_price,    4) if sl_price    else None,
        "tp_price":    round(tp_price,    4) if tp_price    else None,
        "rr":          rr,
        "desc": (f"{best['label']}で転換 {best['elapsed']} ({best['bars']}本前)"),
    }


# ── まとめて実行 ──────────────────────────────────────────
def analyze_entry_points(tf_results: list) -> list:
    """
    A・B・C全てのエントリー分析を実行して返す

    Returns: [ {type, signal, strength, stars, entry_price, sl_price, tp_price, rr, desc}, ... ]
    """
    results = []
    for fn in [analyze_trend_follow, analyze_range_break, analyze_reversal_fresh]:
        try:
            r = fn(tf_results)
            if r:
                results.append(r)
        except Exception as e:
            print(f"  [WARNING] entry analysis error ({fn.__name__}): {e}")

    # 強さの強い順にソート
    results.sort(key=lambda x: x["strength"], reverse=True)
    return results


# ── モメンタム検出（ブレイク前後の足の長さ比較） ────────────
MOMENTUM_PARAMS = {
    "before_bars":  10,  # ブレイク前の比較本数（統計的最適値）
    "after_bars":   1,   # ブレイク後の比較本数（直近1本で即判断）
    "strong_ratio": 2.0, # 強いモメンタムの閾値（ブレイク確認率80%）
    "weak_ratio":   0.8, # フェイクアウト疑いの閾値
}


def analyze_momentum(df: pd.DataFrame,
                     before_bars: int = 5,
                     after_bars: int = 3) -> dict:
    """
    直近のブレイクポイント（STシグナル or スイング転換）前後の
    足の長さ（High-Low）を比較してモメンタムを評価する

    Returns:
    {
        "before_avg": float,   # ブレイク前の平均足長さ
        "after_avg":  float,   # ブレイク後の平均足長さ
        "ratio":      float,   # after / before
        "status":     str,     # "STRONG" / "NORMAL" / "WEAK"
        "label":      str,     # 表示用テキスト
        "color":      str,     # 表示色
        "signal_bar": int,     # シグナル発生バーのインデックス（-N）
        "before_bars": int,
        "after_bars":  int,
    }
    """
    result = {
        "before_avg": None, "after_avg": None, "ratio": None,
        "status": "UNKNOWN", "label": "", "color": "#888",
        "signal_bar": None,
        "before_bars": before_bars, "after_bars": after_bars,
    }

    if len(df) < before_bars + after_bars + 1:
        return result

    # 足の長さ（High - Low）
    candle_len = (df["High"] - df["Low"]).values

    # ブレイクポイントの検出（優先順位順）
    signal_pos = None

    # 1) STシグナル（BUY/SELL）が最優先
    if "st_signal" in df.columns:
        sig_idx = df[df["st_signal"].notna()].index
        if len(sig_idx) > 0:
            # 直近のシグナル
            last_sig = sig_idx[-1]
            pos = df.index.get_loc(last_sig)
            # after_bars分以上の確定足がある場合
            if pos >= before_bars and (len(df) - 1 - pos) >= after_bars:
                signal_pos = pos

    # 2) スイング転換（pivot）をフォールバックとして使用
    if signal_pos is None and "swing_high" in df.columns:
        sh_idx = df[df["swing_high"] == True].index
        sl_idx = df[df["swing_low"]  == True].index
        all_swings = sorted(list(sh_idx) + list(sl_idx),
                            key=lambda x: df.index.get_loc(x))
        if all_swings:
            for sw in reversed(all_swings):
                pos = df.index.get_loc(sw)
                if pos >= before_bars and (len(df) - 1 - pos) >= after_bars:
                    signal_pos = pos
                    break

    # 3) どちらもなければ直近N+M本を使って分割
    if signal_pos is None:
        mid = len(df) - after_bars - 1
        if mid >= before_bars:
            signal_pos = mid

    if signal_pos is None:
        return result

    # ブレイク前後の平均足長さ
    before_slice = candle_len[signal_pos - before_bars : signal_pos]
    after_slice  = candle_len[signal_pos + 1 : signal_pos + 1 + after_bars]

    if len(before_slice) == 0 or len(after_slice) == 0:
        return result

    before_avg = float(np.mean(before_slice))
    after_avg  = float(np.mean(after_slice))

    if before_avg == 0:
        return result

    ratio = after_avg / before_avg

    # ステータス判定
    strong = MOMENTUM_PARAMS["strong_ratio"]
    weak   = MOMENTUM_PARAMS["weak_ratio"]

    if ratio >= strong * 1.5:
        status = "VERY_STRONG"
        label  = f"Momentum ★★★ ({ratio:.1f}x)"
        color  = "#26a69a"
    elif ratio >= strong:
        status = "STRONG"
        label  = f"Momentum ★★  ({ratio:.1f}x)"
        color  = "#58a6ff"
    elif ratio >= 1.0:
        status = "NORMAL"
        label  = f"Momentum ★   ({ratio:.1f}x)"
        color  = "#8b949e"
    elif ratio >= weak:
        status = "WEAK"
        label  = f"Momentum ↓   ({ratio:.1f}x)"
        color  = "#ffa726"
    else:
        status = "FAKE"
        label  = f"Momentum ⚠   ({ratio:.1f}x) Fake?"
        color  = "#ef5350"

    result.update({
        "before_avg":  round(before_avg, 6),
        "after_avg":   round(after_avg, 6),
        "ratio":       round(ratio, 2),
        "status":      status,
        "label":       label,
        "color":       color,
        "signal_bar":  signal_pos - (len(df) - 1),  # 現在足からの距離（負の数）
    })
    return result
