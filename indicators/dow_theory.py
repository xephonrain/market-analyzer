# ============================================================
#  indicators/dow_theory.py
# ============================================================
import pandas as pd
import numpy as np
from datetime import datetime


def detect_swing_points(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    df = df.copy()
    highs = df["High"]
    lows  = df["Low"]
    swing_high = pd.Series(False, index=df.index)
    swing_low  = pd.Series(False, index=df.index)

    for i in range(window, len(df) - window):
        if highs.iloc[i] == highs.iloc[i - window: i + window + 1].max():
            swing_high.iloc[i] = True
        if lows.iloc[i] == lows.iloc[i - window: i + window + 1].min():
            swing_low.iloc[i] = True

    df["swing_high"] = swing_high
    df["swing_low"]  = swing_low
    return df


def _bars_and_time_since(df: pd.DataFrame, target_index) -> dict:
    """
    target_index（スイングポイントの行）から現在足までの
    経過本数・経過時間を計算する
    """
    if target_index is None:
        return {"bars": None, "elapsed_str": None}

    try:
        pos = df.index.get_loc(target_index)
    except KeyError:
        return {"bars": None, "elapsed_str": None}

    bars_ago = len(df) - 1 - pos

    # 経過時間（インデックスがdatetimeの場合）
    try:
        t_then = pd.Timestamp(target_index)
        t_now  = pd.Timestamp(df.index[-1])
        delta  = t_now - t_then
        total_hours = delta.total_seconds() / 3600

        if total_hours < 1:
            elapsed_str = f"{int(delta.total_seconds() / 60)}分前"
        elif total_hours < 24:
            elapsed_str = f"{int(total_hours)}時間前"
        elif total_hours < 24 * 7:
            elapsed_str = f"{int(total_hours / 24)}日前"
        elif total_hours < 24 * 30:
            elapsed_str = f"{int(total_hours / 24 / 7)}週間前"
        else:
            elapsed_str = f"{int(total_hours / 24 / 30)}ヶ月前"
    except Exception:
        elapsed_str = None

    return {"bars": bars_ago, "elapsed_str": elapsed_str}


def analyze_dow_theory(df: pd.DataFrame, window: int = 5, min_swings: int = 4) -> dict:
    """
    ダウ理論でトレンド方向・転換タイミングを判定する

    Returns に追加:
        pivot_time   : トレンド転換が確定したスイングの日時
        bars_since   : 転換確定から現在足までの経過本数
        elapsed_str  : 経過時間の人間向け文字列（例: "3日前"）
        pending      : 転換しそう（片方の条件のみ成立）の状態
        pending_desc : 転換しそうの説明
    """
    df = detect_swing_points(df, window)

    sh = df[df["swing_high"]][["High"]].copy()
    sl = df[df["swing_low"]][["Low"]].copy()

    result = {
        "trend":        "insufficient_data",
        "label":        "データ不足",
        "color":        "#888888",
        "swing_highs":  [],
        "swing_lows":   [],
        "hh": False, "hl": False,
        "lh": False, "ll": False,
        "description":  "",
        # 転換タイミング
        "pivot_time":   None,
        "bars_since":   None,
        "elapsed_str":  None,
        # 転換しそう
        "pending":      False,
        "pending_desc": "",
    }

    if len(sh) < 2 or len(sl) < 2:
        return result

    # 直近4点
    recent_highs      = sh["High"].values[-4:]
    recent_high_idx   = sh.index[-4:].tolist()
    recent_lows       = sl["Low"].values[-4:]
    recent_low_idx    = sl.index[-4:].tolist()

    result["swing_highs"] = [(str(idx.date()), round(float(v), 4))
                              for idx, v in zip(sh.index[-4:], recent_highs)]
    result["swing_lows"]  = [(str(idx.date()), round(float(v), 4))
                              for idx, v in zip(sl.index[-4:], recent_lows)]

    # HH/HL / LH/LL 判定
    if len(recent_highs) >= 2:
        result["hh"] = bool(recent_highs[-1] > recent_highs[-2])
        result["lh"] = bool(recent_highs[-1] < recent_highs[-2])
    if len(recent_lows) >= 2:
        result["hl"] = bool(recent_lows[-1] > recent_lows[-2])
        result["ll"] = bool(recent_lows[-1] < recent_lows[-2])

    # ── トレンド判定 + 転換時刻の特定 ────────────────────
    pivot_index = None

    if result["hh"] and result["hl"]:
        result["trend"]       = "uptrend"
        result["label"]       = "↑ 上昇トレンド"
        result["color"]       = "#26a69a"
        result["description"] = "HH（高値切り上げ）＋HL（安値切り上げ）確認"
        # 転換確定 = HLが確定したスイング安値（より後のもの）
        pivot_index = recent_low_idx[-1]

    elif result["lh"] and result["ll"]:
        result["trend"]       = "downtrend"
        result["label"]       = "↓ 下降トレンド"
        result["color"]       = "#ef5350"
        result["description"] = "LH（高値切り下げ）＋LL（安値切り下げ）確認"
        # 転換確定 = LLが確定したスイング安値
        pivot_index = recent_low_idx[-1]

    elif result["hh"] and result["ll"]:
        result["trend"]       = "range"
        result["label"]       = "→ レンジ（拡大）"
        result["color"]       = "#ffa726"
        result["description"] = "高値切り上げ・安値切り下げ → 拡大レンジ"
        pivot_index = recent_high_idx[-1] if df.index.get_loc(recent_high_idx[-1]) > df.index.get_loc(recent_low_idx[-1]) else recent_low_idx[-1]

    elif result["lh"] and result["hl"]:
        result["trend"]       = "range"
        result["label"]       = "→ レンジ（収縮）"
        result["color"]       = "#ffa726"
        result["description"] = "高値切り下げ・安値切り上げ → 収縮レンジ"
        pivot_index = recent_high_idx[-1] if df.index.get_loc(recent_high_idx[-1]) > df.index.get_loc(recent_low_idx[-1]) else recent_low_idx[-1]

    else:
        result["trend"]       = "range"
        result["label"]       = "→ レンジ"
        result["color"]       = "#ffa726"
        result["description"] = "明確なトレンドなし"
        all_idx = list(recent_high_idx) + list(recent_low_idx)
        if all_idx:
            pivot_index = max(all_idx, key=lambda x: df.index.get_loc(x))

    # ── 経過時間の計算 ───────────────────────────────────
    if pivot_index is not None:
        elapsed = _bars_and_time_since(df, pivot_index)
        result["pivot_time"] = str(pivot_index)[:16]
        result["bars_since"] = elapsed["bars"]
        result["elapsed_str"] = elapsed["elapsed_str"]

    # ── 転換しそう（pending）の判定 ──────────────────────
    #
    # 上昇転換しそう: HHは出たがHLがまだ（安値が前回を下回っている）
    # 下降転換しそう: LLは出たがLHがまだ（高値が前回を上回っている）
    #
    # ただし「現在の足が前回スイングに近づいている」かも見る
    last_close = float(df["Close"].iloc[-1])

    if result["trend"] in ("range", "insufficient_data"):
        if result["hh"] and not result["hl"]:
            # 高値は切り上げた → 安値が切り上がれば上昇確定
            last_low_val = float(recent_lows[-2]) if len(recent_lows) >= 2 else None
            result["pending"]      = True
            result["pending_desc"] = (
                f"⚠️ 上昇転換しそう: 高値切り上げ(HH)確認済 → "
                f"安値 {round(recent_lows[-1],4)} が前回安値 "
                f"{round(last_low_val,4) if last_low_val else '?'} を上回れば確定"
            )
        elif result["ll"] and not result["lh"]:
            # 安値は切り下げた → 高値が切り下がれば下降確定
            last_high_val = float(recent_highs[-2]) if len(recent_highs) >= 2 else None
            result["pending"]      = True
            result["pending_desc"] = (
                f"⚠️ 下降転換しそう: 安値切り下げ(LL)確認済 → "
                f"高値 {round(recent_highs[-1],4)} が前回高値 "
                f"{round(last_high_val,4) if last_high_val else '?'} を下回れば確定"
            )

    return result
