#!/usr/bin/env python3
# ============================================================
#  chart.py  - Lightweight Charts チャート生成
# ============================================================
import json, uuid, os
import pandas as pd
import numpy as np


def _to_unix(index):
    return [int(t.timestamp()) for t in pd.to_datetime(index)]


def build_chart(df: pd.DataFrame, name: str, tf_label: str,
                st_summary: dict, dow_summary: dict,
                entry_points: list = None) -> str:

    df = df.dropna(subset=["Close"]).copy()
    if len(df) < 10:
        return "<p style='color:#888;padding:20px'>No chart</p>"

    # データ多すぎる場合は直近500本に制限（ブラウザの負荷軽減）
    if len(df) > 500:
        df = df.tail(500).copy()

    times = _to_unix(df.index)

    # ローソク
    candles = [{"time":t,"open":round(float(o),6),"high":round(float(h),6),
                "low":round(float(l),6),"close":round(float(c),6)}
               for t,o,h,l,c in zip(times,df["Open"],df["High"],df["Low"],df["Close"])]

    # ST
    st_up, st_down = [], []
    if "supertrend" in df.columns and "st_direction" in df.columns:
        for t,v,d in zip(times,df["supertrend"],df["st_direction"]):
            if pd.isna(v): continue
            pt = {"time":t,"value":round(float(v),6)}
            (st_up if d==1 else st_down).append(pt)

    # マーカー
    markers = []
    if "st_signal" in df.columns:
        for t,sig,lo,hi in zip(times,df["st_signal"],df["Low"],df["High"]):
            if sig=="BUY":
                markers.append({"time":t,"position":"belowBar","color":"#26a69a","shape":"arrowUp","text":"BUY"})
            elif sig=="SELL":
                markers.append({"time":t,"position":"aboveBar","color":"#ef5350","shape":"arrowDown","text":"SELL"})
    if "swing_high" in df.columns:
        for t,f in zip(times,df["swing_high"]):
            if f: markers.append({"time":t,"position":"aboveBar","color":"#f0c040","shape":"circle","text":"H"})
    if "swing_low" in df.columns:
        for t,f in zip(times,df["swing_low"]):
            if f: markers.append({"time":t,"position":"belowBar","color":"#7c83ff","shape":"circle","text":"L"})
    markers.sort(key=lambda x: x["time"])

    # 出来高
    vol_data = []
    if "Volume" in df.columns:
        for t,v,c,o in zip(times,df["Volume"],df["Close"],df["Open"]):
            if pd.isna(v): continue
            color = "rgba(38,166,154,0.6)" if float(c)>=float(o) else "rgba(239,83,80,0.6)"
            vol_data.append({"time":t,"value":float(v),"color":color})

    # ── エントリーポイントのプライスライン ──────────────────
    price_lines = []
    if entry_points:
        for ep in entry_points:
            tp_   = ep.get("type","")
            sig   = ep.get("signal","")
            stars = ep.get("stars","")
            ec    = "#26a69a" if sig in ("BUY","WATCH") else "#ef5350"

            ep_val = ep.get("entry_price") or ep.get("breakout_price")
            if ep_val:
                price_lines.append({"price":ep_val,"color":ec,
                    "lineWidth":2,"lineStyle":0,
                    "title":f"[{tp_}]{stars}","axisLabelVisible":True})
            if ep.get("sl_price"):
                price_lines.append({"price":ep["sl_price"],"color":"#ef5350",
                    "lineWidth":1,"lineStyle":2,
                    "title":f"[{tp_}]SL","axisLabelVisible":True})
            if ep.get("tp_price"):
                price_lines.append({"price":ep["tp_price"],"color":"#26a69a",
                    "lineWidth":1,"lineStyle":2,
                    "title":f"[{tp_}]TP","axisLabelVisible":True})
            if ep.get("breakdown_price") and ep.get("breakdown_price") != ep.get("breakout_price"):
                price_lines.append({"price":ep["breakdown_price"],"color":"#ef5350",
                    "lineWidth":1,"lineStyle":1,
                    "title":"[B]Breakdown","axisLabelVisible":True})

    # BUY/SELLシグナル足の高値・安値ライン（直近3件のみ）
    signal_price_lines = []
    if "st_signal" in df.columns:
        sig_df = df[df["st_signal"].notna()].tail(3)  # 直近3件に制限
        for idx, row in sig_df.iterrows():
            signal_price_lines.append({"price":round(float(row["High"]),6),
                "color":"rgba(240,192,64,0.5)","lineWidth":1,"lineStyle":2,
                "title":"Sig H","axisLabelVisible":False})
            signal_price_lines.append({"price":round(float(row["Low"]),6),
                "color":"rgba(240,192,64,0.3)","lineWidth":1,"lineStyle":2,
                "title":"Sig L","axisLabelVisible":False})

    # ラベル
    dow_label = dow_summary.get("label","")
    dow_color = dow_summary.get("color","#888")
    st_label  = st_summary.get("label","")
    st_color  = st_summary.get("color","#888")

    div_id = f"lw_{uuid.uuid4().hex[:12]}"
    vol_id = f"vl_{uuid.uuid4().hex[:12]}"

    pl_json  = json.dumps(price_lines,  ensure_ascii=False)
    spl_json = json.dumps(signal_price_lines, ensure_ascii=False)

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

  var chart = LC.createChart(document.getElementById("{div_id}"), {{
    layout:{{ background:{{color:"#0d1117"}}, textColor:"#8b949e", fontSize:11 }},
    grid:{{ vertLines:{{color:"#21262d"}}, horzLines:{{color:"#21262d"}} }},
    crosshair:{{ mode:1 }},
    rightPriceScale:{{ borderColor:"#30363d" }},
    timeScale:{{ borderColor:"#30363d", timeVisible:true, secondsVisible:false }},
    handleScroll:true, handleScale:true,
  }});

  var candleSeries = chart.addCandlestickSeries({{
    upColor:"#26a69a", downColor:"#ef5350",
    borderUpColor:"#26a69a", borderDownColor:"#ef5350",
    wickUpColor:"#26a69a", wickDownColor:"#ef5350",
  }});
  candleSeries.setData({json.dumps(candles, ensure_ascii=False)});
  candleSeries.setMarkers({json.dumps(markers, ensure_ascii=False)});

  // プライスライン（エントリー/SL/TP）
  var priceLines = {pl_json};
  priceLines.forEach(function(pl){{ candleSeries.createPriceLine(pl); }});

  // シグナル足の高値・安値ライン
  var sigLines = {spl_json};
  sigLines.forEach(function(pl){{ candleSeries.createPriceLine(pl); }});

  // ST上昇ライン
  var stUp = {json.dumps(st_up, ensure_ascii=False)};
  if(stUp.length>0){{
    var su=chart.addLineSeries({{color:"#26a69a",lineWidth:2,lastValueVisible:false,priceLineVisible:false}});
    su.setData(stUp);
  }}
  // ST下降ライン
  var stDown = {json.dumps(st_down, ensure_ascii=False)};
  if(stDown.length>0){{
    var sd=chart.addLineSeries({{color:"#ef5350",lineWidth:2,lastValueVisible:false,priceLineVisible:false}});
    sd.setData(stDown);
  }}

  // 出来高
  var volChart = LC.createChart(document.getElementById("{vol_id}"), {{
    layout:{{ background:{{color:"#0d1117"}}, textColor:"#8b949e", fontSize:10 }},
    grid:{{ vertLines:{{color:"#21262d"}}, horzLines:{{visible:false}} }},
    rightPriceScale:{{ borderColor:"#30363d", scaleMargins:{{top:0.1,bottom:0}} }},
    timeScale:{{ borderColor:"#30363d", timeVisible:true, secondsVisible:false }},
    handleScroll:false, handleScale:false,
  }});
  var volSeries=volChart.addHistogramSeries({{priceFormat:{{type:"volume"}},priceScaleId:"right"}});
  volSeries.setData({json.dumps(vol_data, ensure_ascii=False)});

  chart.timeScale().subscribeVisibleLogicalRangeChange(function(r){{ if(r) volChart.timeScale().setVisibleLogicalRange(r); }});
  volChart.timeScale().subscribeVisibleLogicalRangeChange(function(r){{ if(r) chart.timeScale().setVisibleLogicalRange(r); }});

  var ro=new ResizeObserver(function(){{
    var el=document.getElementById("{div_id}");
    if(el){{ chart.applyOptions({{width:el.clientWidth}}); volChart.applyOptions({{width:el.clientWidth}}); }}
  }});
  ro.observe(document.getElementById("{div_id}"));

  chart.timeScale().fitContent();
  volChart.timeScale().fitContent();
}})();
</script>'''


def get_lw_charts_js() -> str:
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "lw_charts.js"),
        os.path.join(os.path.dirname(__file__), "lw_charts.js"),
        "lw_charts.js",
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read()
    print("  [WARNING] lw_charts.js not found")
    return ""
