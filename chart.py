#!/usr/bin/env python3
# ============================================================
#  chart.py  - Lightweight Charts (TradingView) ベースのチャート生成
#  CDN不要・完全オフライン動作・iOS Safari対応
# ============================================================
import json
import uuid
import pandas as pd
import numpy as np


def _to_unix(index):
    """DatetimeIndexをUnixタイムスタンプ（秒）のリストに変換"""
    return [int(t.timestamp()) for t in pd.to_datetime(index)]


def build_chart(df: pd.DataFrame, name: str, tf_label: str,
                st_summary: dict, dow_summary: dict) -> str:
    """
    Lightweight Charts v5 を使ったチャートHTML断片を返す。
    CDN不要（JSはHTMLに埋め込み済み）。

    表示内容:
      - ローソク足
      - スーパートレンドライン（上昇=緑 / 下降=赤）
      - BUY/SELL マーカー
      - スイング高値・安値マーカー
      - 出来高バー（下段）
    """
    df = df.dropna(subset=["Close"]).copy()
    if len(df) < 10:
        return "<p style='color:#888;padding:20px'>データ不足</p>"

    times = _to_unix(df.index)

    # ── ローソクデータ ─────────────────────────────────────
    candles = [
        {"time": t, "open": round(float(o), 6), "high": round(float(h), 6),
         "low": round(float(l), 6), "close": round(float(c), 6)}
        for t, o, h, l, c in zip(
            times, df["Open"], df["High"], df["Low"], df["Close"]
        )
    ]

    # ── スーパートレンドライン（2系列に分割） ──────────────
    st_up_data, st_down_data = [], []
    if "supertrend" in df.columns and "st_direction" in df.columns:
        for t, v, d in zip(times, df["supertrend"], df["st_direction"]):
            if pd.isna(v):
                continue
            pt = {"time": t, "value": round(float(v), 6)}
            if d == 1:
                st_up_data.append(pt)
            else:
                st_down_data.append(pt)

    # ── BUY/SELL マーカー ──────────────────────────────────
    markers = []
    if "st_signal" in df.columns:
        for t, sig, lo, hi in zip(times, df["st_signal"], df["Low"], df["High"]):
            if sig == "BUY":
                markers.append({
                    "time": t, "position": "belowBar",
                    "color": "#26a69a", "shape": "arrowUp", "text": "BUY"
                })
            elif sig == "SELL":
                markers.append({
                    "time": t, "position": "aboveBar",
                    "color": "#ef5350", "shape": "arrowDown", "text": "SELL"
                })

    # ── スイング高値安値マーカー ───────────────────────────
    if "swing_high" in df.columns:
        for t, flag in zip(times, df["swing_high"]):
            if flag:
                markers.append({
                    "time": t, "position": "aboveBar",
                    "color": "#f0c040", "shape": "circle", "text": "H"
                })
    if "swing_low" in df.columns:
        for t, flag in zip(times, df["swing_low"]):
            if flag:
                markers.append({
                    "time": t, "position": "belowBar",
                    "color": "#7c83ff", "shape": "circle", "text": "L"
                })

    # time順ソート（マーカーはソートが必要）
    markers.sort(key=lambda x: x["time"])

    # ── 出来高 ─────────────────────────────────────────────
    vol_data = []
    if "Volume" in df.columns:
        for t, v, c, o in zip(times, df["Volume"], df["Close"], df["Open"]):
            if pd.isna(v):
                continue
            color = "rgba(38,166,154,0.6)" if float(c) >= float(o) else "rgba(239,83,80,0.6)"
            vol_data.append({"time": t, "value": float(v), "color": color})

    # ── ラベル用 ───────────────────────────────────────────
    dow_label = dow_summary.get("label", "")
    dow_color = dow_summary.get("color", "#888")
    st_label  = st_summary.get("label", "")
    st_color  = st_summary.get("color", "#888")

    div_id  = f"lw_{uuid.uuid4().hex[:12]}"
    vol_id  = f"vl_{uuid.uuid4().hex[:12]}"

    candles_json  = json.dumps(candles,  ensure_ascii=False)
    st_up_json    = json.dumps(st_up_data,   ensure_ascii=False)
    st_down_json  = json.dumps(st_down_data, ensure_ascii=False)
    markers_json  = json.dumps(markers,  ensure_ascii=False)
    vol_json      = json.dumps(vol_data, ensure_ascii=False)

    return f'''
<div style="position:relative;margin-bottom:4px;">
  <div style="position:absolute;top:6px;right:8px;z-index:10;
       background:#161b22cc;border:1px solid #30363d;border-radius:4px;
       padding:3px 8px;font-size:11px;color:#e6edf3;pointer-events:none;">
    <b>{tf_label}</b>
    &nbsp;ST:<span style="color:{st_color}">{st_label}</span>
    &nbsp;Dow:<span style="color:{dow_color}">{dow_label}</span>
  </div>
  <div id="{div_id}" style="height:280px;width:100%;"></div>
  <div id="{vol_id}" style="height:70px;width:100%;margin-top:2px;"></div>
</div>
<script>
(function(){{
  var LC = window.LightweightCharts;
  if (!LC) {{ console.error("LightweightCharts not loaded"); return; }}

  // ── メインチャート ──
  var chart = LC.createChart(document.getElementById("{div_id}"), {{
    layout: {{
      background: {{ color: "#0d1117" }},
      textColor:  "#8b949e",
      fontSize:   11,
    }},
    grid: {{
      vertLines: {{ color: "#21262d" }},
      horzLines: {{ color: "#21262d" }},
    }},
    crosshair: {{ mode: LC.CrosshairMode ? LC.CrosshairMode.Normal : 1 }},
    rightPriceScale: {{ borderColor: "#30363d" }},
    timeScale: {{
      borderColor: "#30363d",
      timeVisible: true,
      secondsVisible: false,
    }},
    handleScroll: true,
    handleScale:  true,
  }});

  // ローソク足
  var candleSeries = chart.addCandlestickSeries({{
    upColor:        "#26a69a",
    downColor:      "#ef5350",
    borderUpColor:  "#26a69a",
    borderDownColor:"#ef5350",
    wickUpColor:    "#26a69a",
    wickDownColor:  "#ef5350",
  }});
  candleSeries.setData({candles_json});
  candleSeries.setMarkers({markers_json});

  // ST上昇ライン
  var stUp = {st_up_json};
  if (stUp.length > 0) {{
    var stUpSeries = chart.addLineSeries({{
      color: "#26a69a", lineWidth: 2,
      lastValueVisible: false, priceLineVisible: false,
    }});
    stUpSeries.setData(stUp);
  }}

  // ST下降ライン
  var stDown = {st_down_json};
  if (stDown.length > 0) {{
    var stDownSeries = chart.addLineSeries({{
      color: "#ef5350", lineWidth: 2,
      lastValueVisible: false, priceLineVisible: false,
    }});
    stDownSeries.setData(stDown);
  }}

  // ── 出来高チャート ──
  var volChart = LC.createChart(document.getElementById("{vol_id}"), {{
    layout: {{
      background: {{ color: "#0d1117" }},
      textColor: "#8b949e",
      fontSize: 10,
    }},
    grid: {{
      vertLines: {{ color: "#21262d" }},
      horzLines: {{ visible: false }},
    }},
    rightPriceScale: {{
      borderColor: "#30363d",
      scaleMargins: {{ top: 0.1, bottom: 0 }},
    }},
    timeScale: {{
      borderColor: "#30363d",
      timeVisible: true,
      secondsVisible: false,
    }},
    handleScroll: false,
    handleScale:  false,
  }});

  var volSeries = volChart.addHistogramSeries({{
    priceFormat: {{ type: "volume" }},
    priceScaleId: "right",
  }});
  volSeries.setData({vol_json});

  // 時間軸を同期
  chart.timeScale().subscribeVisibleLogicalRangeChange(function(range) {{
    if (range) volChart.timeScale().setVisibleLogicalRange(range);
  }});
  volChart.timeScale().subscribeVisibleLogicalRangeChange(function(range) {{
    if (range) chart.timeScale().setVisibleLogicalRange(range);
  }});

  // リサイズ対応
  var resizeObs = new ResizeObserver(function() {{
    var el = document.getElementById("{div_id}");
    if (el) {{
      chart.applyOptions({{ width: el.clientWidth }});
      volChart.applyOptions({{ width: el.clientWidth }});
    }}
  }});
  resizeObs.observe(document.getElementById("{div_id}"));

  // 全データ表示
  chart.timeScale().fitContent();
  volChart.timeScale().fitContent();
}})();
</script>'''


# ── JSバンドルを読み込む（report.pyから呼び出す） ──────────
import os

def get_lw_charts_js() -> str:
    """Lightweight Charts のJSを返す（HTMLへの埋め込み用）"""
    js_path = os.path.join(os.path.dirname(__file__), "lw_charts.js")
    if os.path.exists(js_path):
        with open(js_path, encoding="utf-8") as f:
            return f.read()
    return ""
