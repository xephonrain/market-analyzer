#!/usr/bin/env python3
# ============================================================
#  report.py  - HTMLレポート生成（新UI版）
# ============================================================
from datetime import datetime
import json as _json
from config import OUTPUT, PICKUP_CONDITIONS

# ── アイコンマップ ────────────────────────────────────────
CATEGORY_ICONS = {
    "Metals":    "🥇",
    "FX":        "💱",
    "US Stocks": "🇺🇸",
    "JP Stocks": "🇯🇵",
    "Crypto":    "₿",
}

def _cat_icon(cat):
    return CATEGORY_ICONS.get(cat, "📊")

def _ep_type_label(t):
    return {"A":"TF","B":"RB","C":"TR"}.get(t, t)

def _score_color(direction):
    return {"up":"var(--up)","down":"var(--down)"}.get(direction,"var(--rng)")

def _tf_direction(st, dow):
    """STとダウ理論から総合方向を返す"""
    st_dir  = (st  or {}).get("direction", 0)
    dow_tr  = (dow or {}).get("trend", "range")
    if st_dir == 1 and dow_tr == "uptrend":   return "up"
    if st_dir == -1 and dow_tr == "downtrend": return "down"
    return "range"

def _fmt_price(v):
    if v is None: return "-"
    if v >= 1000: return f"{v:,.2f}"
    if v >= 10:   return f"{v:.3f}"
    return f"{v:.5f}"


# ── ホット銘柄（折りたたみ） ──────────────────────────────
def _hot_section(hot_list):
    if not hot_list: return ""
    tabs_h = "".join(
        f'<button class="ht {"on" if i==0 else ""}" '
        f'style="--tc:{sc["color"]}" onclick="htab(\'{sc["id"]}\',this)">'
        f'{sc["icon"]} {sc["label"]}</button>'
        for i, sc in enumerate(hot_list))

    tabs_b = ""
    for i, sc in enumerate(hot_list):
        active = "on" if i == 0 else ""
        if sc.get("error") or not sc.get("stocks"):
            body = '<div class="hot-empty">No data</div>'
        else:
            rows = ""
            for s in sc["stocks"]:
                pct = s.get("change_pct_str","-")
                pos = s.get("positive", True)
                pc  = "var(--up)" if pos else "var(--down)"
                ar  = "▲" if pos else "▼"
                vr  = s.get("vol_ratio")
                vb  = f'<span class="vbadge">{vr}x</span>' if vr and vr >= 2 else ""
                rows += (f'<div class="hot-row">'
                         f'<div><span class="htk">{s.get("ticker","")}</span>'
                         f'<span class="hnm">{s.get("name","")}</span></div>'
                         f'<div class="hr">'
                         f'<span class="hprice">{s.get("price_str","-")}</span>'
                         f'<span class="hpct" style="color:{pc}">{ar}{pct}</span>'
                         f'<span class="hvol">{s.get("volume_str","-")}{vb}</span>'
                         f'</div></div>')
            body = f'<div class="hot-rows">{rows}</div>'
        tabs_b += f'<div class="hpane {active}" id="hp-{sc["id"]}">{body}</div>'

    return f'''
<div class="hot-section" id="sec-hot">
  <div class="hot-hdr" onclick="toggleSec(\'sec-hot\')">
    <span class="hot-title">📡 Market Trends <span class="hot-src">Yahoo Finance</span></span>
    <span class="arr" id="arr-sec-hot">▲</span>
  </div>
  <div class="sec-body" id="body-sec-hot" style="display:none">
    <div class="htabs">{tabs_h}</div>
    {tabs_b}
  </div>
</div>'''


# ── ピックアップストリップ ────────────────────────────────
def _pickup_strip(pickup_list):
    if not pickup_list:
        return ""
    pills = ""
    for p in pickup_list:
        color = _score_color(p["direction"])
        mid   = f'modal_{p["ticker"].replace("=","").replace("^","").replace(".","")}'
        pills += (f'<div class="pp" style="border-color:{color}" onclick="openModal(\'{mid}\')">'
                  f'<div class="pp-name">{p["name"]}</div>'
                  f'<div class="pp-dir" style="color:{color}">'
                  f'{"↑" if p["direction"]=="up" else "↓"} {p["label"]}</div>'
                  f'<div class="pp-score">TF {p["agree"]}本 · {p["score"]:.0f}pt</div>'
                  f'</div>')
    return f'''
<div class="pickup-strip">
  <div class="pickup-label">★ Pickup</div>
  <div class="pickup-scroll">{pills}</div>
</div>'''


# ── ピックアップモーダル ──────────────────────────────────
def _pickup_modals(pickup_list, symbol_info_map):
    modals = ""
    for p in pickup_list:
        mid   = f'modal_{p["ticker"].replace("=","").replace("^","").replace(".","")}'
        info  = symbol_info_map.get(p["ticker"], {})
        color = _score_color(p["direction"])
        arrow = "↑" if p["direction"] == "up" else "↓"

        # 基本情報
        basic = ""
        for lbl, val in [
            ("Sector",      info.get("sector")),
            ("Market Cap",  info.get("market_cap")),
            ("52W High",    str(info["week52_high"]) if info.get("week52_high") else None),
            ("52W Low",     str(info["week52_low"])  if info.get("week52_low")  else None),
            ("vs 52W High", f'{info["pct_from_high"]:+.1f}%' if info.get("pct_from_high") is not None else None),
            ("Target",      f'${info["target_price"]}' if info.get("target_price") else None),
        ]:
            if val:
                basic += f'<div class="mrow"><span class="mlbl">{lbl}</span><span>{val}</span></div>'

        # イベント
        events = ""
        for lbl, val in [
            ("📅 Earnings",    info.get("earnings_date")),
            ("💸 Ex-Div",      info.get("ex_dividend_date")),
        ]:
            if val:
                events += f'<div class="mrow"><span class="mlbl">{lbl}</span><span>{val}</span></div>'

        # アナリスト
        rec_html = ""
        rb = info.get("rec_buy",0) or 0
        rh = info.get("rec_hold",0) or 0
        rs = info.get("rec_sell",0) or 0
        total = rb + rh + rs
        if total > 0:
            bp = rb/total*100; hp = rh/total*100; sp = rs/total*100
            rk = info.get("recommendation","")
            rc = "#26a69a" if "buy" in (rk or "") else "#ffa726" if rk=="hold" else "#ef5350"
            rec_html = (f'<div class="msub">Analysts</div>'
                        f'<div class="rec-bar-wrap">'
                        f'<div style="width:{bp:.0f}%;background:#26a69a;height:100%"></div>'
                        f'<div style="width:{hp:.0f}%;background:#ffa726;height:100%"></div>'
                        f'<div style="width:{sp:.0f}%;background:#ef5350;height:100%"></div>'
                        f'</div>'
                        f'<div class="rec-lbl">'
                        f'<span style="color:#26a69a">Buy {rb}</span>'
                        f'<span style="color:#ffa726">Hold {rh}</span>'
                        f'<span style="color:#ef5350">Sell {rs}</span>'
                        f'<span style="color:{rc};font-weight:700;margin-left:auto">{(rk or "").upper()}</span>'
                        f'</div>')

        # 需給
        supply = ""
        for lbl, val in [
            ("Short Ratio",  f'{info["short_ratio"]:.1f}d' if info.get("short_ratio") else None),
            ("Short Float",  f'{info["short_float_pct"]*100:.1f}%' if info.get("short_float_pct") else None),
            ("Insider",      f'{info["held_pct_insiders"]*100:.1f}%' if info.get("held_pct_insiders") else None),
            ("Institution",  f'{info["held_pct_institutions"]*100:.1f}%' if info.get("held_pct_institutions") else None),
        ]:
            if val:
                supply += f'<div class="mrow"><span class="mlbl">{lbl}</span><span>{val}</span></div>'

        # ニュース
        news_html = ""
        for n in info.get("news", []):
            href = f' href="{n["link"]}" target="_blank"' if n.get("link") else ""
            news_html += (f'<a class="news-item"{href}>'
                          f'<span class="ndate">{n.get("date","")}</span>'
                          f'<span class="ntitle">{n.get("title","")}</span></a>')
        if news_html:
            news_html = f'<div class="msub">News</div><div class="news-list">{news_html}</div>'

        # エントリー
        ep_html = ""
        for ep in p.get("entry_points", []):
            sig = ep.get("signal","")
            cls = "buy" if sig=="BUY" else "sell" if sig=="SELL" else "watch"
            rr  = f' · RR {ep["rr"]}' if ep.get("rr") else ""
            ep_html += (f'<div class="ep-row">'
                        f'<span class="ep-badge {cls}">[{_ep_type_label(ep["type"])}]{ep["stars"]} {sig}</span>'
                        f'<span class="ep-price">Entry {_fmt_price(ep.get("entry_price") or ep.get("breakout_price"))}'
                        f' · SL {_fmt_price(ep.get("sl_price"))} · TP {_fmt_price(ep.get("tp_price"))}{rr}</span>'
                        f'</div>')

        # AI
        ai_html = ""
        ai = p.get("ai_comment","")
        if ai:
            ai_html = f'<div class="mai">🤖 {ai}</div>'

        modals += (f'<div class="modal-ov" id="{mid}" onclick="closeModalOut(event,\'{mid}\')">'
                   f'<div class="modal-box">'
                   f'<div class="modal-hdr" style="border-left:4px solid {color}">'
                   f'<div><div class="mname">{p["name"]}</div>'
                   f'<div class="mtkr">{p["ticker"]} · {p["category"]}</div></div>'
                   f'<button class="mx" onclick="closeModal(\'{mid}\')">×</button></div>'
                   f'<div class="modal-body">'
                   f'<div class="mtrend" style="color:{color}">{arrow} {p["label"]} · {p["score"]:.0f}pt</div>'
                   f'{ep_html}'
                   f'{"<div class=msub>Info</div>" + basic if basic else ""}'
                   f'{"<div class=msub>Events</div>" + events if events else ""}'
                   f'{rec_html}'
                   f'{"<div class=msub>Supply & Demand</div>" + supply if supply else ""}'
                   f'{news_html}'
                   f'{ai_html}'
                   f'</div></div></div>')
    return modals


# ── 検索バー ─────────────────────────────────────────────
def _search_bar(categories):
    chips = "".join(
        f'<span class="chip" data-cat="{c}" onclick="togCat(this)">{c}</span>'
        for c in categories)
    return f'''
<div class="search-row">
  <input id="si" type="search" class="search-input" placeholder="Search symbol..."
    oninput="onSearch(this.value)" autocapitalize="none" autocorrect="off">
</div>
<div class="filter-bar">
  <span class="chip on" data-trend="all"  onclick="togTrend(this)">All</span>
  <span class="chip up" data-trend="up"   onclick="togTrend(this)">↑ Up</span>
  <span class="chip dn" data-trend="down" onclick="togTrend(this)">↓ Down</span>
  <span class="chip"    data-sort="score" onclick="togSort(this)">Score↓</span>
  <span class="chip"    data-sort="pickup" onclick="togSort(this)">★ Only</span>
  {chips}
</div>
<div id="rc" class="result-count"></div>'''


# ── TFグリッドセル ────────────────────────────────────────
def _tf_cell(tf, res):
    st  = res.get("st")  or {}
    dow = res.get("dow") or {}
    mom = res.get("momentum") or {}

    # データ取得失敗の場合
    if not st or st.get("label") == "N/A" or not dow or dow.get("label") == "データ不足":
        return (f'<div class="tf-cell na-cell">'
                f'<div class="tf-name">{tf["label"]}</div>'
                f'<div class="tf-icon" style="color:var(--dim)">—</div>'
                f'<div class="tf-sub" style="color:var(--dim)">No data</div>'
                f'</div>')

    direction = _tf_direction(st, dow)
    elapsed   = dow.get("elapsed_str")
    bars      = dow.get("bars_since")
    pending   = dow.get("pending", False)
    st_lbl    = "↑" if st.get("direction")==1 else "↓" if st.get("direction")==-1 else "→"
    dow_lbl   = "↑" if dow.get("trend")=="uptrend" else "↓" if dow.get("trend")=="downtrend" else "→"

    cell_cls  = "tf-cell up-cell" if direction=="up" else "tf-cell dn-cell" if direction=="down" else "tf-cell rng-cell"
    icon_col  = "var(--up)" if direction=="up" else "var(--down)" if direction=="down" else "var(--rng)"
    icon      = "↑" if direction=="up" else "↓" if direction=="down" else "→"

    sub = f'ST{st_lbl} {dow.get("label","")[:4] if dow.get("label") else "?"}'

    # ピボット表示
    pivot = ""
    if elapsed and bars is not None:
        pivot = f'<div class="tf-pivot">{elapsed}</div>'
    elif pending:
        pivot = '<div class="tf-pivot" style="color:var(--gold)">⚠Pend</div>'

    # モメンタム（pivotがある場合は省略してスコアのみ）
    mom_html = ""
    if mom.get("ratio") is not None:
        ratio = mom["ratio"]
        mc    = mom.get("color","#888")
        stars = "●●●" if ratio>=2.5 else "●●" if ratio>=2.0 else "●" if ratio>=1.2 else "○"
        mom_html = f'<div class="tf-pivot" style="color:{mc}">{stars}{ratio:.1f}x</div>'

    # pivotとmomを1行にまとめる
    sub2 = ""
    if pivot and mom_html:
        # pivotとmomが両方ある場合はpivotのみ（スペース節約）
        sub2 = pivot
    elif pivot:
        sub2 = pivot
    elif mom_html:
        sub2 = mom_html

    return (f'<div class="{cell_cls}">'
            f'<div class="tf-name">{tf["label"]}</div>'
            f'<div class="tf-icon" style="color:{icon_col}">{icon}</div>'
            f'<div class="tf-sub">{sub}</div>'
            f'{sub2}'
            f'</div>')


# ── 銘柄カード ────────────────────────────────────────────
def _symbol_card(item):
    sym        = item["symbol"]
    tf_results = item["tf_results"]
    mtf        = item["mtf_score"]
    price_info = item.get("price_info") or {}
    ai_comment = item.get("ai_comment") or ""
    entry_pts  = item.get("entry_points") or []
    is_pickup  = item.get("is_pickup", False)

    sid   = sym["ticker"].replace("=","").replace("^","").replace(".","")
    score_col = _score_color(mtf["direction"])
    arrow = "↑" if mtf["direction"]=="up" else "↓" if mtf["direction"]=="down" else "→"

    # TFグリッド
    tf_cells = "".join(_tf_cell(tf, res) for tf, res in tf_results)

    # 価格バー
    pos_html = ""
    cur = price_info.get("current")
    sh  = price_info.get("swing_high")
    sl  = price_info.get("swing_low")
    pos = price_info.get("range_position")
    pfh = price_info.get("pct_from_high")
    pfl = price_info.get("pct_from_low")
    if cur and sh and sl and pos is not None:
        dot_col = "var(--up)" if pos>60 else "var(--down)" if pos<40 else "var(--rng)"
        sh_str  = _fmt_price(sh) + (f' ({pfh:+.1f}%)' if pfh is not None else "")
        sl_str  = _fmt_price(sl) + (f' ({pfl:+.1f}%)' if pfl is not None else "")
        pos_html = (f'<div class="pos-bar-wrap">'
                    f'<span class="pos-label">{sl_str}</span>'
                    f'<div class="pos-bar">'
                    f'<div class="pos-dot" style="left:{pos:.0f}%;background:{dot_col}"></div>'
                    f'</div>'
                    f'<span class="pos-label right">{sh_str}</span>'
                    f'<span class="pos-pct" style="color:{dot_col}">{pos:.0f}%</span>'
                    f'</div>')
    elif cur:
        pos_html = (f'<div class="pos-bar-wrap">'
                    f'<span class="pos-label">Now: {_fmt_price(cur)}</span>'
                    f'</div>')

    # エントリー
    ep_html = ""
    for ep in entry_pts[:2]:
        sig = ep.get("signal","")
        cls = "buy" if sig=="BUY" else "sell" if sig=="SELL" else "watch"
        rr  = f' · RR {ep["rr"]}' if ep.get("rr") else ""
        ep_v = ep.get("entry_price") or ep.get("breakout_price")
        ep_html += (f'<div class="entry-row">'
                    f'<span class="ep-badge {cls}">[{_ep_type_label(ep["type"])}]{ep["stars"]} {sig}</span>'
                    f'<span class="ep-price">Entry {_fmt_price(ep_v)}'
                    f' · SL {_fmt_price(ep.get("sl_price"))} · TP {_fmt_price(ep.get("tp_price"))}{rr}</span>'
                    f'</div>')

    # AI（タップで全文展開）
    ai_html = ""
    if ai_comment:
        ai_id = f"ai_{sid}"
        # 改行を<br>に変換
        ai_body = ai_comment.replace('\n', '<br>')
        ai_html = (f'<div class="ai-row" id="{ai_id}" onclick="toggleAI(&quot;{ai_id}&quot;)">'
                   f'<span class="ai-icon">🤖</span>'
                   f'<span class="ai-text collapsed">{ai_body}</span>'
                   f'<span class="ai-more">▼</span>'
                   f'</div>')

    # Now表示（pos_htmlがない場合の現在値）
    card_cls = "sym-card pickup-card" if is_pickup else "sym-card"

    return (f'<div class="{card_cls}" id="card_{sid}" '
            f'data-name="{sym["name"]}" data-ticker="{sym["ticker"]}" '
            f'data-cat="{sym["category"]}" data-score="{mtf["score"]}" '
            f'data-trend="{mtf["direction"]}" data-pickup="{str(is_pickup).lower()}">'

            # ヘッダー
            f'<div class="card-top">'
            f'<div class="sym-icon">{_cat_icon(sym["category"])}</div>'
            f'<div class="sym-main">'
            f'<div class="sym-name-row">'
            f'<span class="sym-name">{sym["name"]}</span>'
            f'<span class="sym-ticker">{sym["ticker"]}</span>'
            f'<span class="sym-cat">{sym["category"]}</span>'
            f'</div>'
            f'</div>'
            f'<div class="score-pill">'
            f'<span class="score-num" style="color:{score_col}">{mtf["score"]:.0f}</span>'
            f'<span class="score-label">{arrow} pt</span>'
            f'</div>'
            f'</div>'

            # 価格バー
            f'{pos_html}'

            # TFグリッド
            f'<div class="tf-grid">{tf_cells}</div>'

            # エントリー
            f'{ep_html}'

            # AI
            f'{ai_html}'

            f'</div>')


# ── メイン ────────────────────────────────────────────────
def generate_html(all_results, pickup_list, chart_html_map=None,
                  hot_list=None, symbol_info_map=None):
    if symbol_info_map is None: symbol_info_map = {}

    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    refresh_meta = ""
    if OUTPUT.get("auto_refresh_minutes", 0) > 0:
        secs = OUTPUT["auto_refresh_minutes"] * 60
        refresh_meta = f'<meta http-equiv="refresh" content="{secs}">'

    pickup_tickers = {p["ticker"] for p in pickup_list}
    for item in all_results:
        item["is_pickup"] = item["symbol"]["ticker"] in pickup_tickers

    categories = list(dict.fromkeys(i["symbol"]["category"] for i in all_results))
    json_cats  = _json.dumps(list(categories))

    # カードをカテゴリ別にグループ化
    grouped = {}
    for item in all_results:
        cat = item["symbol"]["category"]
        grouped.setdefault(cat, []).append(item)

    cards_html = ""
    for cat, items in grouped.items():
        cards_html += f'<div class="sec-head">{cat}</div>'
        cards_html += "".join(_symbol_card(i) for i in items)

    modals    = _pickup_modals(pickup_list, symbol_info_map)
    total     = len(all_results)
    pu_count  = len(pickup_list)

    from chart import get_lw_charts_js
    lw_js = get_lw_charts_js()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Market">
  <meta name="theme-color" content="#0d1117">
  <link rel="manifest" href="/market-analyzer/manifest.json">
  <link rel="apple-touch-icon" href="/market-analyzer/icon-192.png">
  {refresh_meta}
  <title>{OUTPUT['title']}</title>
  <script>{lw_js}</script>
  <style>
:root{{--ink:#0d1117;--ink2:#141b24;--ink3:#1c2533;--line:#243040;
      --text:#e2eaf4;--dim:#6b7f96;
      --up:#00d4aa;--down:#ff4e6a;--rng:#f5a623;--gold:#f0c040;--blue:#4a9eff;
      --up-bg:rgba(0,212,170,.08);--dn-bg:rgba(255,78,106,.08);}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--ink);color:var(--text);font-family:-apple-system,'SF Pro Text','Helvetica Neue',sans-serif;font-size:14px;}}

/* Header */
header{{padding:14px 16px 10px;display:flex;align-items:center;gap:10px;
        border-bottom:1px solid var(--line);position:sticky;top:0;
        background:var(--ink);z-index:100;
        padding-top:calc(14px + env(safe-area-inset-top,0px));}}
.logo{{font-size:15px;font-weight:700;letter-spacing:-.3px;}}
.logo span{{color:var(--up);}}
.hright{{margin-left:auto;display:flex;align-items:center;gap:8px;}}
.badge-pickup{{background:var(--gold);color:#000;font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px;}}
.btn-run{{background:var(--blue);border:none;color:#fff;font-size:12px;font-weight:700;padding:6px 12px;border-radius:6px;cursor:pointer;}}
.btn-reload{{background:var(--ink3);border:1px solid var(--line);color:var(--dim);font-size:14px;padding:5px 9px;border-radius:6px;cursor:pointer;}}
.utime{{font-size:11px;color:var(--dim);}}

/* Filter */
.filter-bar{{padding:8px 12px;display:flex;gap:6px;overflow-x:auto;border-bottom:1px solid var(--line);}}
.filter-bar::-webkit-scrollbar{{display:none;}}
.chip{{background:var(--ink3);border:1px solid var(--line);color:var(--dim);border-radius:20px;padding:5px 12px;font-size:12px;white-space:nowrap;cursor:pointer;transition:all .15s;}}
.chip.on{{background:var(--blue);border-color:var(--blue);color:#fff;}}
.chip.up{{background:var(--up-bg);border-color:var(--up);color:var(--up);}}
.chip.dn{{background:var(--dn-bg);border-color:var(--down);color:var(--down);}}

/* Search */
.search-row{{padding:8px 12px;}}
.search-input{{width:100%;background:var(--ink3);border:1px solid var(--line);border-radius:8px;color:var(--text);padding:8px 12px;font-size:14px;outline:none;}}
.search-input:focus{{border-color:var(--blue);}}
.search-input::placeholder{{color:var(--dim);}}
.result-count{{padding:2px 14px 4px;font-size:11px;color:var(--dim);min-height:16px;}}

main{{padding:6px 12px calc(40px + env(safe-area-inset-bottom,0px));max-width:900px;margin:0 auto;}}

/* Hot */
.hot-section{{background:var(--ink2);border:1px solid var(--line);border-radius:10px;margin-bottom:10px;overflow:hidden;}}
.hot-hdr{{padding:10px 14px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;}}
.hot-hdr:hover{{background:var(--ink3);}}
.hot-title{{font-size:13px;font-weight:700;}}
.hot-src{{font-size:10px;color:var(--dim);margin-left:6px;}}
.arr{{font-size:10px;color:var(--dim);}}
.sec-body{{}}
.htabs{{display:flex;background:var(--ink3);border-bottom:1px solid var(--line);padding:0 10px;gap:3px;overflow-x:auto;}}
.ht{{background:none;border:none;color:var(--dim);padding:7px 12px;font-size:12px;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;}}
.ht.on{{color:var(--tc,var(--text));border-bottom-color:var(--tc,var(--blue));}}
.hpane{{display:none;}}
.hpane.on{{display:block;}}
.hot-rows{{padding:6px 0;}}
.hot-row{{display:flex;align-items:center;justify-content:space-between;padding:7px 14px;border-bottom:1px solid var(--line);}}
.hot-row:last-child{{border-bottom:none;}}
.htk{{font-size:13px;font-weight:700;display:block;}}
.hnm{{font-size:11px;color:var(--dim);max-width:120px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.hr{{display:flex;align-items:center;gap:8px;}}
.hprice{{font-size:12px;}}
.hpct{{font-size:12px;font-weight:700;}}
.hvol{{font-size:11px;color:var(--dim);}}
.vbadge{{font-size:9px;background:rgba(240,192,64,.2);color:var(--gold);padding:1px 5px;border-radius:3px;font-weight:700;margin-left:3px;}}
.hot-empty{{padding:14px;color:var(--dim);font-size:13px;}}

/* Pickup strip */
.pickup-strip{{margin-bottom:10px;}}
.pickup-label{{font-size:11px;color:var(--gold);font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;padding:0 2px;}}
.pickup-scroll{{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;}}
.pickup-scroll::-webkit-scrollbar{{display:none;}}
.pp{{background:var(--ink2);border:1px solid var(--line);border-radius:10px;padding:9px 13px;flex-shrink:0;min-width:130px;cursor:pointer;transition:opacity .15s;}}
.pp:hover{{opacity:.8;}}
.pp-name{{font-size:13px;font-weight:700;margin-bottom:2px;}}
.pp-dir{{font-size:11px;font-weight:600;}}
.pp-score{{font-size:10px;color:var(--dim);margin-top:2px;}}

/* Section head */
.sec-head{{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.07em;padding:10px 2px 6px;border-bottom:1px solid var(--line);margin-bottom:6px;}}

/* Symbol card */
.sym-card{{background:var(--ink2);border:1px solid var(--line);border-radius:12px;margin-bottom:8px;overflow:hidden;transition:border-color .15s;}}
.sym-card:hover{{border-color:var(--blue);}}
.sym-card.pickup-card{{border-color:var(--gold);}}

.card-top{{padding:12px 14px 8px;display:flex;align-items:center;gap:10px;}}
.sym-icon{{width:36px;height:36px;border-radius:10px;background:var(--ink3);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}}
.sym-main{{flex:1;min-width:0;}}
.sym-name-row{{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;}}
.sym-name{{font-size:15px;font-weight:700;}}
.sym-ticker{{font-size:11px;color:var(--dim);}}
.sym-cat{{font-size:10px;padding:1px 6px;border-radius:4px;background:var(--ink3);color:var(--dim);margin-left:auto;}}
.score-pill{{display:flex;flex-direction:column;align-items:flex-end;gap:2px;flex-shrink:0;}}
.score-num{{font-size:22px;font-weight:800;line-height:1;letter-spacing:-.5px;}}
.score-label{{font-size:10px;color:var(--dim);}}

/* Price bar */
.pos-bar-wrap{{padding:0 14px 8px;display:flex;align-items:center;gap:6px;}}
.pos-label{{font-size:10px;color:var(--dim);flex-shrink:0;}}
.pos-label.right{{text-align:right;}}
.pos-bar{{flex:1;height:4px;background:var(--ink3);border-radius:2px;position:relative;}}
.pos-dot{{position:absolute;top:50%;transform:translate(-50%,-50%);width:10px;height:10px;border-radius:50%;border:2px solid var(--ink2);}}
.pos-pct{{font-size:10px;font-weight:700;width:28px;text-align:right;flex-shrink:0;}}

/* TF grid */
.tf-grid{{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid var(--line);}}
.tf-cell{{padding:7px 3px 7px;text-align:center;border-right:1px solid var(--line);display:flex;flex-direction:column;gap:2px;align-items:center;}}
.tf-cell:last-child{{border-right:none;}}
.tf-name{{font-size:9px;color:var(--dim);text-transform:uppercase;letter-spacing:.03em;}}
.tf-icon{{font-size:18px;line-height:1;}}
.tf-sub{{font-size:8px;color:var(--dim);line-height:1.2;max-width:100%;overflow:hidden;}}
.up-cell{{background:rgba(0,212,170,.04);}}
.dn-cell{{background:rgba(255,78,106,.04);}}
.rng-cell{{background:rgba(245,166,35,.03);}}
.tf-pivot{{font-size:8px;color:var(--dim);text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;padding:0 1px;}}

/* Entry */
.entry-row{{padding:7px 14px;border-top:1px solid var(--line);display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
.ep-badge{{font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;flex-shrink:0;}}
.ep-badge.buy{{background:var(--up-bg);color:var(--up);border:1px solid var(--up);}}
.ep-badge.sell{{background:var(--dn-bg);color:var(--down);border:1px solid var(--down);}}
.ep-badge.watch{{background:rgba(245,166,35,.1);color:var(--rng);border:1px solid var(--rng);}}
.ep-price{{font-size:11px;color:var(--dim);}}
.ep-rr{{font-size:11px;font-weight:700;color:var(--blue);margin-left:auto;}}

/* AI */
.ai-row{{padding:8px 14px 10px;border-top:1px solid var(--line);font-size:12px;color:var(--dim);line-height:1.6;display:flex;gap:6px;align-items:flex-start;background:rgba(74,158,255,.04);cursor:pointer;user-select:none;}}
.ai-row:hover{{background:rgba(74,158,255,.08);}}
.ai-icon{{flex-shrink:0;}}
.ai-text{{flex:1;}}
.ai-text.collapsed{{overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;}}
.ai-text.expanded{{display:block;}}
.ai-more{{flex-shrink:0;font-size:10px;color:var(--blue);align-self:flex-end;transition:transform .2s;}}
.ai-more.open{{transform:rotate(180deg);}}

/* Modal */
.modal-ov{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:500;align-items:flex-end;justify-content:center;}}
.modal-ov.open{{display:flex;}}
.modal-box{{background:var(--ink2);border-radius:16px 16px 0 0;width:100%;max-width:600px;max-height:85dvh;overflow-y:auto;}}
.modal-hdr{{padding:14px 16px;display:flex;align-items:flex-start;justify-content:space-between;border-bottom:1px solid var(--line);}}
.mname{{font-size:17px;font-weight:700;}}
.mtkr{{font-size:12px;color:var(--dim);margin-top:2px;}}
.mx{{background:var(--ink3);border:none;color:var(--dim);width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;}}
.modal-body{{padding:14px 16px;display:flex;flex-direction:column;gap:10px;}}
.mtrend{{font-size:16px;font-weight:700;}}
.msub{{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em;margin-top:4px;}}
.mrow{{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--line);font-size:13px;}}
.mrow:last-child{{border-bottom:none;}}
.mlbl{{color:var(--dim);}}
.rec-bar-wrap{{display:flex;height:7px;border-radius:4px;overflow:hidden;gap:1px;}}
.rec-lbl{{display:flex;font-size:12px;gap:10px;margin-top:4px;}}
.ep-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:4px 0;}}
.mai{{font-size:12px;color:var(--dim);line-height:1.6;padding:8px;background:rgba(74,158,255,.06);border-radius:6px;}}
.news-list{{display:flex;flex-direction:column;gap:5px;}}
.news-item{{display:flex;flex-direction:column;gap:2px;padding:8px;background:var(--ink3);border-radius:6px;text-decoration:none;color:inherit;}}
.news-item:hover{{background:#243040;}}
.ndate{{font-size:10px;color:var(--dim);}}
.ntitle{{font-size:13px;line-height:1.4;}}

#no-results{{display:none;padding:32px;text-align:center;color:var(--dim);}}

@media(max-width:380px){{
  .tf-icon{{font-size:16px;}}
  .score-num{{font-size:18px;}}
  .card-top{{padding:10px 10px 6px;gap:8px;}}
}}
  </style>
</head>
<body>
<header>
  <div class="logo">Market<span>Pulse</span></div>
  <div class="utime">⏱ {now}</div>
  <div class="hright">
    <span class="badge-pickup">★ {pu_count}</span>
    <button class="btn-reload" onclick="location.reload()">↻</button>
    <button class="btn-run" id="run-btn" onclick="runAnalysis()">▶ Run</button>
  </div>
</header>

{_search_bar(categories)}

<main>
  {_hot_section(hot_list or [])}
  {_pickup_strip(pickup_list)}
  <div id="cc">{cards_html}</div>
  <div id="no-results">No symbols found</div>
</main>

{modals}

<script>
// ── Section toggle ──
function toggleSec(id){{
  var b=document.getElementById('body-'+id);
  var a=document.getElementById('arr-'+id);
  if(b.style.display==='none'){{b.style.display='';a.textContent='▲';}}
  else{{b.style.display='none';a.textContent='▼';}}
}}
// ── Hot tabs ──
function htab(id,btn){{
  document.querySelectorAll('.ht').forEach(b=>b.classList.remove('on'));
  document.querySelectorAll('.hpane').forEach(p=>p.classList.remove('on'));
  btn.classList.add('on');
  document.getElementById('hp-'+id).classList.add('on');
}}
// ── Modal ──
function openModal(id){{var el=document.getElementById(id);if(el){{el.classList.add('open');document.body.style.overflow='hidden';}}}}
function closeModal(id){{var el=document.getElementById(id);if(el){{el.classList.remove('open');document.body.style.overflow='';}}}}
function closeModalOut(e,id){{if(e.target===e.currentTarget)closeModal(id);}}

// ── Filter / Search ──
var _cats=new Set({json_cats}),_trend='all',_sort='default',_q='';

function onSearch(v){{_q=v.trim().toLowerCase();applyFilter();}}
function togTrend(btn){{
  var isTrend=['all','up','down'].includes(btn.dataset.trend);
  if(!isTrend)return;
  document.querySelectorAll('[data-trend]').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  _trend=btn.dataset.trend;
  applyFilter();
}}
function togSort(btn){{
  if(btn.classList.contains('on')){{btn.classList.remove('on');_sort='default';}}
  else{{
    document.querySelectorAll('[data-sort]').forEach(b=>b.classList.remove('on'));
    btn.classList.add('on');
    _sort=btn.dataset.sort;
  }}
  applyFilter();
}}
function togCat(btn){{
  var c=btn.dataset.cat;
  if(!c)return;
  if(_cats.has(c)){{_cats.delete(c);btn.classList.remove('on');}}
  else{{_cats.add(c);btn.classList.add('on');}}
  applyFilter();
}}
function applyFilter(){{
  var cc=document.getElementById('cc');
  var cards=Array.from(cc.querySelectorAll('.sym-card'));
  var vis=[];
  cards.forEach(function(c){{
    var n=(c.dataset.name||'').toLowerCase(),t=(c.dataset.ticker||'').toLowerCase();
    var ok=_cats.has(c.dataset.cat)
      &&(_trend==='all'||c.dataset.trend===_trend)
      &&(_sort!=='pickup'||c.dataset.pickup==='true')
      &&(!_q||n.includes(_q)||t.includes(_q));
    c.style.display=ok?'':'none';
    if(ok)vis.push(c);
  }});
  // section headings
  cc.querySelectorAll('.sec-head').forEach(function(h){{
    var next=h.nextElementSibling;
    var hasVisible=false;
    while(next&&!next.classList.contains('sec-head')){{
      if(next.style.display!=='none')hasVisible=true;
      next=next.nextElementSibling;
    }}
    h.style.display=hasVisible?'':'none';
  }});
  if(_sort==='score'){{
    vis.sort((a,b)=>parseFloat(b.dataset.score)-parseFloat(a.dataset.score));
    vis.forEach(c=>cc.appendChild(c));
  }}
  var rc=document.getElementById('rc');
  rc.textContent=(_q||_trend!=='all'||_sort!=='default')?vis.length+' / '+cards.length+' shown':'';
  document.getElementById('no-results').style.display=vis.length===0?'block':'none';
}}

// ── Run Analysis ──
function runAnalysis(){{
  var repo=localStorage.getItem('gh_repo')||'';
  var token=localStorage.getItem('gh_token')||'';
  if(!repo){{repo=prompt('GitHub repo (e.g. user/market-analyzer):');if(!repo)return;localStorage.setItem('gh_repo',repo);}}
  if(!token){{token=prompt('GitHub Token:');if(!token)return;localStorage.setItem('gh_token',token);}}
  var btn=document.getElementById('run-btn');
  btn.textContent='...';btn.disabled=true;
  fetch('https://api.github.com/repos/'+repo+'/actions/workflows/analyze.yml/dispatches',{{
    method:'POST',
    headers:{{'Authorization':'Bearer '+token,'Content-Type':'application/json'}},
    body:JSON.stringify({{ref:'main'}})
  }}).then(function(r){{
    if(r.status===204){{
      btn.textContent='✓ Triggered';btn.style.background='var(--up)';
      setTimeout(function(){{btn.textContent='▶ Run';btn.style.background='';btn.disabled=false;}},3000);
    }}else{{throw new Error('HTTP '+r.status);}}
  }}).catch(function(e){{
    alert('Error: '+e.message);
    btn.textContent='▶ Run';btn.disabled=false;
  }});
}}

// Toggle AI comment
function toggleAI(id){{
  var row  = document.getElementById(id);
  var text = row.querySelector('.ai-text');
  var more = row.querySelector('.ai-more');
  if(text.classList.contains('collapsed')){{
    text.classList.remove('collapsed');
    text.classList.add('expanded');
    more.classList.add('open');
  }}else{{
    text.classList.remove('expanded');
    text.classList.add('collapsed');
    more.classList.remove('open');
  }}
}}

// Init
document.querySelectorAll('[data-cat]').forEach(function(b){{
  if(b.dataset.cat&&_cats.has(b.dataset.cat))b.classList.add('on');
}});
</script>
</body>
</html>'''
