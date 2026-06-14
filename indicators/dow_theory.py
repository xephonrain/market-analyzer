# ============================================================
#  indicators/dow_theory.py
# ============================================================
import pandas as pd
import numpy as np


def detect_swing_points(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    スイングハイ・スイングローを検出する

    window: 前後N本よりも高い/低いものをスイングポイントとする
    """
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


def analyze_dow_theory(df: pd.DataFrame, window: int = 5, min_swings: int = 4) -> dict:
    """
    ダウ理論でトレンド方向を判定する

    Returns:
        {
          "trend"        : "uptrend" / "downtrend" / "range" / "insufficient_data",
          "label"        : 表示用文字列,
          "color"        : カラーコード,
          "swing_highs"  : [(index, value), ...],
          "swing_lows"   : [(index, value), ...],
          "hh": bool,  "hl": bool,  # 上昇トレンド条件
          "lh": bool,  "ll": bool,  # 下降トレンド条件
          "description"  : 詳細説明,
        }
    """
    df = detect_swing_points(df, window)

    sh = df[df["swing_high"]][["High"]].copy()
    sl = df[df["swing_low"]][["Low"]].copy()

    result = {
        "trend":       "insufficient_data",
        "label":       "データ不足",
        "color":       "#888888",
        "swing_highs": [],
        "swing_lows":  [],
        "hh": False, "hl": False,
        "lh": False, "ll": False,
        "description": "",
    }

    if len(sh) < 2 or len(sl) < 2:
        return result

    # 直近スイングを取得
    recent_highs = sh["High"].values[-4:]  # 直近4点
    recent_lows  = sl["Low"].values[-4:]

    result["swing_highs"] = [(str(idx.date()), round(float(v), 4))
                              for idx, v in zip(sh.index[-4:], recent_highs)]
    result["swing_lows"]  = [(str(idx.date()), round(float(v), 4))
                              for idx, v in zip(sl.index[-4:], recent_lows)]

    # HH/HL / LH/LL 判定（直近2スイング間で比較）
    if len(recent_highs) >= 2:
        result["hh"] = bool(recent_highs[-1] > recent_highs[-2])  # 高値切り上げ
        result["lh"] = bool(recent_highs[-1] < recent_highs[-2])  # 高値切り下げ

    if len(recent_lows) >= 2:
        result["hl"] = bool(recent_lows[-1] > recent_lows[-2])   # 安値切り上げ
        result["ll"] = bool(recent_lows[-1] < recent_lows[-2])   # 安値切り下げ

    # トレンド判定
    if result["hh"] and result["hl"]:
        result["trend"] = "uptrend"
        result["label"] = "↑ 上昇トレンド"
        result["color"] = "#26a69a"
        result["description"] = "HH（高値切り上げ）＋HL（安値切り上げ）確認"
    elif result["lh"] and result["ll"]:
        result["trend"] = "downtrend"
        result["label"] = "↓ 下降トレンド"
        result["color"] = "#ef5350"
        result["description"] = "LH（高値切り下げ）＋LL（安値切り下げ）確認"
    elif result["hh"] and result["ll"]:
        result["trend"] = "range"
        result["label"] = "→ レンジ（拮抗）"
        result["color"] = "#ffa726"
        result["description"] = "高値切り上げ・安値切り下げ → 拡大レンジ"
    elif result["lh"] and result["hl"]:
        result["trend"] = "range"
        result["label"] = "→ レンジ（収縮）"
        result["color"] = "#ffa726"
        result["description"] = "高値切り下げ・安値切り上げ → 収縮レンジ"
    else:
        result["trend"] = "range"
        result["label"] = "→ レンジ"
        result["color"] = "#ffa726"
        result["description"] = "明確なトレンドなし"

    return result
