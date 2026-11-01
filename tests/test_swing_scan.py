"""swing_scan の検算用テスト（ネットワーク不要・合成データ）。
実行: python3 tests/test_swing_scan.py
"""
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import swing_scan as ss  # noqa: E402

ENV = {"SWING_CAPITAL": "100000", "SWING_MAX_LOSS": "5000"}
CFG = ss.load_cfg(env=ENV)


def make_df(n=520, base=500.0, slope=0.3, amp=40.0, period=12.0, seed=1, vol=2_000_000):
    rng = np.random.default_rng(seed)
    i = np.arange(n)
    close = base + slope * i + amp * np.sin(i / period) + rng.normal(0, 0.6, n)
    idx = pd.bdate_range("2024-06-03", periods=n, tz="Asia/Tokyo")
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.02
    low = np.minimum(open_, close) * 0.98
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": np.full(n, vol, dtype=float)}, index=idx)


def test_sizing():
    c = CFG
    assert ss.size_position(800, 760, c) == 100          # 損失4,000円 / 資金8万円
    assert ss.size_position(950, 890, c) is None         # 100株だと損失6,000円 > 5,000円
    assert ss.size_position(1000, 960, c) == 100         # 資金ちょうど10万円
    assert ss.size_position(1001, 960, c) is None        # 資金超過
    assert ss.size_position(500, 500, c) is None         # 損切り幅ゼロ
    assert ss.size_position(500, 510, c) is None         # 損切りが上


def test_candidate_invariants():
    """上昇トレンドの合成データを末尾位置を変えながら判定し、出た候補が常に制約を満たすこと"""
    df = make_df()
    hits = 0
    for k in range(300, 520, 3):
        r, why = ss.evaluate(df.iloc[:k], CFG)
        if not r:
            continue
        hits += 1
        e, s = r["entry"], r["stop"]
        assert s < e <= r["close"] + 1, (k, r)
        n = ss.size_position(e, s, CFG)
        assert n is not None and n * (e - s) <= CFG["max_loss"] and n * e <= CFG["capital"], (k, r)
        assert r["rr_to_recent_high"] >= CFG["min_rr"] - 1e-9
        assert r["risk_per_100"] == round((e - s) * 100)
    assert hits > 0, "上昇トレンドなのに候補が一度も出ない"


def test_downtrend_never_trend_signal():
    df = make_df(slope=-0.3, base=900)
    for k in range(300, 520, 3):
        r, why = ss.evaluate(df.iloc[:k], CFG)
        if r:
            assert r["kind"] != "trend", (k, r)


def test_filters():
    df = make_df()
    r, why = ss.evaluate(df.assign(Close=df.Close * 3, High=df.High * 3, Low=df.Low * 3, Open=df.Open * 3), CFG)
    assert why == "too_expensive"
    r, why = ss.evaluate(df.assign(Volume=1000.0), CFG)
    assert why == "low_turnover"
    flat = df.copy()
    flat["High"], flat["Low"] = flat["Close"] * 1.001, flat["Close"] * 0.999
    flat["Open"] = flat["Close"]
    r, why = ss.evaluate(flat, CFG)
    assert why == "low_vol"


def test_pipeline_and_privacy():
    up = make_df()
    ends = [k for k in range(300, 520) if ss.evaluate(up.iloc[:k], CFG)[0]]
    assert ends, "候補が出る末尾位置が見つからない"
    k = ends[-1]
    good = up.iloc[:k]
    down = make_df(slope=-0.3, base=900).iloc[:k]
    pricey = make_df(base=3000, amp=100, slope=0.4).iloc[:k]
    data = {"1111.T": good, "2222.T": down, "3333.T": pricey}
    uni = pd.DataFrame({"ticker": list(data), "name": ["上昇", "下落", "高額"],
                        "market": ["プライム（内国株式）"] * 3, "code": ["1111", "2222", "3333"]})

    def fetch(tickers, period, chunk, pause):
        n = 22 if period == "1mo" else 520
        return {t: data[t].tail(n) for t in tickers if t in data}

    out = ss.run(CFG, fetch=fetch, universe=uni)
    tops = [c["ticker"] for c in out["top"]]
    assert tops == ["1111.T"], (tops, out["funnel"])
    assert out["funnel"]["universe"] == 3 and out["funnel"]["stage1"] <= 2

    # 公開リポジトリ向け: 金額・株数が出力に含まれない
    with tempfile.TemporaryDirectory() as td:
        cfg = dict(CFG, out_json=os.path.join(td, "o.json"), out_log=os.path.join(td, "l.csv"))
        ss.write_outputs(out, {**cfg, "out_json": os.path.relpath(cfg["out_json"], ss.BASE),
                               "out_log": os.path.relpath(cfg["out_log"], ss.BASE)})
        text = open(cfg["out_json"], encoding="utf-8").read()
        for bad in ("capital", "max_loss", "shares", "SWING_"):
            assert bad not in text, bad
        assert os.path.exists(cfg["out_log"])


def test_dow_default_behavior_unchanged():
    """dedupe_ties=False(既定)は従来アルゴリズムと完全一致。Trueは同値の隣接ピボットを1点にする"""
    from indicators.dow_theory import detect_swing_points
    rng = np.random.default_rng(7)
    n, w = 400, 5
    close = np.round(300 + np.cumsum(rng.normal(0, 3, n)))          # 1円刻み → 同値が出やすい
    idx = pd.bdate_range("2024-01-01", periods=n)
    df = pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1.0}, index=idx)
    old_h, old_l = [False] * n, [False] * n
    for i in range(w, n - w):                                         # 従来ロジックをそのまま再実装
        old_h[i] = df["High"].iloc[i] == df["High"].iloc[i - w:i + w + 1].max()
        old_l[i] = df["Low"].iloc[i] == df["Low"].iloc[i - w:i + w + 1].min()
    new = detect_swing_points(df, w)
    assert list(new["swing_high"]) == old_h and list(new["swing_low"]) == old_l
    ded = detect_swing_points(df, w, dedupe_ties=True)
    assert ded["swing_high"].sum() <= new["swing_high"].sum() and ded["swing_low"].sum() <= new["swing_low"].sum()
    assert (ded["swing_high"] & ~new["swing_high"]).sum() == 0          # 増えない（部分集合）
    # 同値が隣接するピボットが残っていないこと
    hi = df["High"][ded["swing_high"]]
    pos = np.flatnonzero(ded["swing_high"].values)
    for a, b in zip(pos[:-1], pos[1:]):
        assert not (b - a <= w and df["High"].iloc[a] == df["High"].iloc[b])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
    print("all passed")
