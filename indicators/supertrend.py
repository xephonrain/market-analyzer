# ============================================================
#  indicators/supertrend.py
# ============================================================
import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Average True Range を計算"""
    high = df["High"]
    low  = df["Low"]
    close = df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return atr


def calculate_supertrend(df: pd.DataFrame, atr_period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    スーパートレンドを計算して df にカラムを追加して返す

    追加カラム:
        st_upper    : 上バンド
        st_lower    : 下バンド
        supertrend  : 現在のトレンドライン値
        st_direction: 1=上昇(緑) / -1=下降(赤)
        st_signal   : 'BUY' / 'SELL' / None（シグナル発生タイミング）
    """
    df = df.copy()
    atr = calculate_atr(df, atr_period)

    hl2 = (df["High"] + df["Low"]) / 2
    upper_basic = hl2 + multiplier * atr
    lower_basic = hl2 - multiplier * atr

    upper = upper_basic.copy()
    lower = lower_basic.copy()
    direction = pd.Series(index=df.index, dtype=int)
    supertrend = pd.Series(index=df.index, dtype=float)

    for i in range(1, len(df)):
        # 上バンド調整
        if upper_basic.iloc[i] < upper.iloc[i - 1] or df["Close"].iloc[i - 1] > upper.iloc[i - 1]:
            upper.iloc[i] = upper_basic.iloc[i]
        else:
            upper.iloc[i] = upper.iloc[i - 1]

        # 下バンド調整
        if lower_basic.iloc[i] > lower.iloc[i - 1] or df["Close"].iloc[i - 1] < lower.iloc[i - 1]:
            lower.iloc[i] = lower_basic.iloc[i]
        else:
            lower.iloc[i] = lower.iloc[i - 1]

        # 方向判定
        prev_dir = direction.iloc[i - 1] if i > 1 else 1
        if prev_dir == -1 and df["Close"].iloc[i] > upper.iloc[i]:
            direction.iloc[i] = 1
        elif prev_dir == 1 and df["Close"].iloc[i] < lower.iloc[i]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = prev_dir

        supertrend.iloc[i] = lower.iloc[i] if direction.iloc[i] == 1 else upper.iloc[i]

    direction.iloc[0] = 1
    supertrend.iloc[0] = lower.iloc[0]

    df["st_upper"]     = upper
    df["st_lower"]     = lower
    df["supertrend"]   = supertrend
    df["st_direction"] = direction

    # シグナル（方向転換した足）
    df["st_signal"] = None
    changed = direction != direction.shift(1)
    df.loc[changed & (direction == 1),  "st_signal"] = "BUY"
    df.loc[changed & (direction == -1), "st_signal"] = "SELL"

    return df


def get_supertrend_summary(df: pd.DataFrame) -> dict:
    """最新のスーパートレンド状態をサマリーとして返す"""
    latest = df.dropna(subset=["st_direction"]).iloc[-1]
    direction = int(latest["st_direction"])

    return {
        "direction":  direction,
        "label":      "↑ 上昇" if direction == 1 else "↓ 下降",
        "color":      "#26a69a" if direction == 1 else "#ef5350",
        "value":      round(float(latest["supertrend"]), 4),
        "close":      round(float(latest["Close"]), 4),
        "signal":     latest["st_signal"],
    }
