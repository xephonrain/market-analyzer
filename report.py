#!/usr/bin/env python3
# ============================================================
#  report.py
# ============================================================
from datetime import datetime
from collections import defaultdict
import json as _json
from config import OUTPUT, PICKUP_CONDITIONS


def _badge(label, color):
    return f'<span class="badge" style="background:{color}">{label}</span>'

def _score_bar(score, color):
    return (f'<div class="score-bar-wrap">'
            f'<div class="score-bar" style="width:{score}%;background:{color}"></div>'
            f'<span class="score-num">{score:.0f}</span></div>')

def _signal_tag(signal):
    if not signal: return ""
    sc = "#26a69a" if signal == "BUY" else "#ef5350"
    return f'<span class="signal-tag" style="background:{sc}">{signal}</span>'


# ── ホット銘柄 ────────────────────────────────────────────
def _hot_section(hot_list):
    if not hot_list: return ""
    tabs_head = ""
    tabs_body = ""
    for i, sc in enumerate(hot_list):
        active = "active" if i == 0 else ""
        tabs_head += (f'<button class="hot-tab {active}" '
                      f'style="--tc:{sc["color"]}" '
                      f'onclick="switchHotTab(\'{sc["id"]}\',this)">'
                      f'{sc["icon"]} {sc["label"]}</button>')
        if sc.get("error"):
            body = f'<div class="hot-error">Error: {sc["error"]}</div>'
        elif not sc.get("stocks"):
            body = '<div class="hot-error">No data</div>'
        else:
            rows = ""
            for s in sc["stocks"]:
                pct   = s.get("change_pct_str", "-")
                pos   = s.get("positive", True)
                pc    = "#26a69a" if pos else "#ef5350"
                arrow = "&#9650;" if pos else "&#9660;"
                vr    = s.get("vol_ratio")
                vb    = f'<span class="vol-badge">{vr}x</span>' if vr and vr >= 2 else ""
                rows += (f'<tr>'
                         f'<td><span class="hot-ticker">{s.get("ticker","")}</span>'
                         f'<span class="hot-name">{s.get("name","")}</span></td>'
                         f'<td class="num">{s.get("price_str","-")}</td>'
                         f'<td class="num" style="color:{pc}">{arrow}{pct}</td>'
                         f'<td class="num">{s.get("volume_str","-")}{vb}</td>'
                         f'<td class="num mktcap">{s.get("market_cap_str","-")}</td>'
                         f'</tr>')
            body = (f'<table class="hot-table">'
                    f'<thead><tr><th>Symbol</th><th>Price</th>'
                    f'<th>Change</th><th>Volume</th><th>Mkt Cap</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>')
        tabs_body += f'<div class="hot-pane {active}" id="hot-{sc["id"]}">{body}</div>'

    return f'''
<section class="collapsible-section" id="sec-hot">
  <div class="sec-header" onclick="toggleSec(\'sec-hot\')">
    <span>&#128225; Market Trends <span class="src-badge">Yahoo Finance</span></span>
    <span class="arrow" id="arr-sec-hot">&#9650;</span>
  </div>
  <div class="sec-body" id="body-sec-hot">
    <div class="hot-tabs">{tabs_head}</div>
    <div>{tabs_body}</div>
  </div>
</section>'''


# ── ピックアップ ──────────────────────────────────────────
def _pickup_section(pickup_list, symbol_info_map):
    cond = PICKUP_CONDITIONS
    desc = (f"MTF >= {cond['mtf_score_threshold']}pt / "
            f"TF >= {cond['min_tf_agreement']} / Dow / ST align")

    if not pickup_list:
        body = '<div class="pickup-empty">No symbols matched</div>'
    else:
        cards = ""
        for p in pickup_list:
            arrow   = "&#9650;" if p["direction"] == "up" else "&#9660;"
            elapsed = p.get("elapsed_str","")
            bars    = p.get("bars_since")
            pivot   = f' / Pivot {elapsed} / {bars}b' if elapsed and bars is not None else ""
            info    = symbol_info_map.get(p["ticker"], {})
            mid     = f'modal_{p["ticker"].replace("=","").replace("^","").replace(".","")}'
            earn_b  = (f'<span class="ev-badge earn">&#128200; {info["earnings_date"]}</span>'
                       if info.get("earnings_date") else "")
            div_b   = (f'<span class="ev-badge div">&#128181; {info["ex_dividend_date"]}</span>'
                       if info.get("ex_dividend_date") else "")
            cards += (f'<div class="pickup-card" style="border-left:4px solid {p["color"]}"'
                      f' onclick="openModal(\'{mid}\')">'
                      f'<div class="pc-header">'
                      f'<span class="pc-name">{p["name"]}</span>'
                      f'<span class="pc-ticker">{p["ticker"]}</span>'
                      f'<span class="pc-cat">{p["category"]}</span></div>'
                      f'<div class="pc-dir" style="color:{p["color"]}">{arrow} {p["label"]}</div>'
                      f'<div class="pc-meta">TF: {p["agree"]} match{pivot}</div>'
                      f'{earn_b}{div_b}'
                      f'{_score_bar(p["score"], p["color"])}'
                      f'<div class="pc-hint">Tap for details &#8250;</div>'
                      f'</div>')
        body = f'<div class="pickup-grid">{cards}</div>'

    return f'''
<section class="pickup-section">
  <div class="pickup-title">&#11088; Pickup <span class="pickup-cnt">{len(pickup_list)}</span>
    <span class="pickup-cond">{desc}</span></div>
  {body}
</section>'''


# ── ピックアップモーダル ──────────────────────────────────
def _pickup_modals(pickup_list, symbol_info_map):
    modals = ""
    for p in pickup_list:
        mid   = f'modal_{p["ticker"].replace("=","").replace("^","").replace(".","")}'
        info  = symbol_info_map.get(p["ticker"], {})
        color = p["color"]
        arrow = "&#9650;" if p["direction"] == "up" else "&#9660;"

        rows_basic = ""
        for label, val in [
            ("Sector",       info.get("sector")),
            ("Industry",     info.get("industry")),
            ("Market Cap",   info.get("market_cap")),
            ("52W High",     str(info["week52_high"]) if info.get("week52_high") else None),
            ("52W Low",      str(info["week52_low"])  if info.get("week52_low")  else None),
            ("vs 52W High",  f'{info["pct_from_high"]:+.1f}%' if info.get("pct_from_high") is not None else None),
            ("Target Price", f'${info["target_price"]}' if info.get("target_price") else None),
            ("Analysts",     f'{info["analyst_count"]}' if info.get("analyst_count") else None),
        ]:
            if val:
                rows_basic += f'<tr><td class="il">{label}</td><td>{val}</td></tr>'

        rows_events = ""
        for label, val in [
            ("&#128200; Earnings",     info.get("earnings_date")),
            ("&#128181; Ex-Dividend",  info.get("ex_dividend_date")),
            ("&#128176; Dividend Pay", info.get("dividend_date")),
        ]:
            if val:
                rows_events += f'<tr><td class="il">{label}</td><td>{val}</td></tr>'

        rec_html = ""
        rb = info.get("rec_buy",0) or 0
        rh = info.get("rec_hold",0) or 0
        rs = info.get("rec_sell",0) or 0
        total = rb + rh + rs
        if total > 0:
            bp = rb/total*100; hp = rh/total*100; sp = rs/total*100
            rk = info.get("recommendation","")
            rc = "#26a69a" if "buy" in (rk or "") else "#ffa726" if rk=="hold" else "#ef5350"
            rec_html = (f'<div class="modal-sub">Analyst Recommendations</div>'
                        f'<div class="rec-bar-wrap">'
                        f'<div class="rec-bar" style="width:{bp:.0f}%;background:#26a69a"></div>'
                        f'<div class="rec-bar" style="width:{hp:.0f}%;background:#ffa726"></div>'
                        f'<div class="rec-bar" style="width:{sp:.0f}%;background:#ef5350"></div>'
                        f'</div>'
                        f'<div class="rec-labels">'
                        f'<span style="color:#26a69a">Buy {rb}</span>'
                        f'<span style="color:#ffa726">Hold {rh}</span>'
                        f'<span style="color:#ef5350">Sell {rs}</span>'
                        f'<span style="color:{rc};font-weight:700;margin-left:auto">{(rk or "").upper()}</span>'
                        f'</div>')

        upg_html = ""
        for u in info.get("upgrades", []):
            ac = u.get("action","")
            ac_c = "#26a69a" if "up" in ac.lower() else "#ef5350" if "down" in ac.lower() else "#888"
            upg_html += (f'<tr><td>{u.get("date","")}</td><td>{u.get("firm","")}</td>'
                         f'<td style="color:{ac_c}">{ac}</td>'
                         f'<td>{u.get("from","")} -> {u.get("to","")}</td></tr>')
        if upg_html:
            upg_html = f'<div class="modal-sub">Rating Changes</div><table class="upg-table"><tbody>{upg_html}</tbody></table>'

        news_html = ""
        for n in info.get("news", []):
            link  = n.get("link","")
            href  = f' href="{link}" target="_blank"' if link else ""
            news_html += (f'<a class="news-item"{href}>'
                          f'<span class="news-date">{n.get("date","")}</span>'
                          f'<span class="news-title">{n.get("title","")}</span></a>')
        if news_html:
            news_html = f'<div class="modal-sub">News</div><div class="news-list">{news_html}</div>'

        modals += (f'<div class="modal-overlay" id="{mid}" onclick="closeModalOut(event,\'{mid}\')">'
                   f'<div class="modal-box">'
                   f'<div class="modal-hdr" style="border-left:4px solid {color}">'
                   f'<div><div class="modal-name">{p["name"]}</div>'
                   f'<div class="modal-tkr">{p["ticker"]} / {p["category"]}</div></div>'
                   f'<button class="modal-x" onclick="closeModal(\'{mid}\')">x</button></div>'
                   f'<div class="modal-body">'
                   f'<div class="modal-trend" style="color:{color}">{arrow} {p["label"]}</div>'
                   f'{"<table class=info-table>" + rows_basic + "</table>" if rows_basic else ""}'
                   f'{"<div class=modal-sub>Events</div><table class=info-table>" + rows_events + "</table>" if rows_events else ""}'
                   f'{rec_html}{upg_html}{news_html}'
                   f'{"<div class=modal-no-data>No additional data</div>" if not rows_basic and not rows_events else ""}'
                   f'</div></div></div>')
    return modals


# ── 検索バー ─────────────────────────────────────────────
def _search_bar(categories):
    cat_opts = "".join(
        f'<button class="fb active" data-cat="{c}" onclick="togCat(this)">{c}</button>'
        for c in categories)
    return f'''
<div class="search-bar">
  <div class="sw">
    <span class="si">&#128269;</span>
    <input id="si" type="search" placeholder="Symbol / ticker..."
      oninput="onSearch(this.value)" autocapitalize="none" autocorrect="off">
    <button id="sc" onclick="clearSearch()" style="display:none">x</button>
  </div>
  <div class="fr">
    <div class="fg">
      <button class="fb tb active" data-trend="all"   onclick="togTrend(this)">All</button>
      <button class="fb tb"        data-trend="up"    onclick="togTrend(this)">&#8593;Up</button>
      <button class="fb tb"        data-trend="down"  onclick="togTrend(this)">&#8595;Down</button>
      <button class="fb tb"        data-trend="range" onclick="togTrend(this)">&#8594;Range</button>
    </div>
    <div class="fg">{cat_opts}</div>
    <div class="fg">
      <button class="fb sb active" data-sort="default" onclick="togSort(this)">Default</button>
      <button class="fb sb"        data-sort="score"   onclick="togSort(this)">Score&#8595;</button>
      <button class="fb sb"        data-sort="pickup"  onclick="togSort(this)">&#11088;Only</button>
    </div>
  </div>
  <div id="rc" style="font-size:11px;color:#8b949e;margin-top:6px;min-height:14px;"></div>
</div>'''


# ── シンボルカード（新デザイン） ──────────────────────────
def _symbol_card(item, chart_html_map):
    sym  = item["symbol"]
    tf_r = item["tf_results"]
    mtf  = item["mtf_score"]
    sid  = sym["ticker"].replace("=","").replace("^","").replace(".","")
    cid  = f"card_{sid}"

    # TFサマリー行（常時表示）
    tf_rows = ""
    for tf, res in tf_r:
        st  = res.get("st")  or {}
        dow = res.get("dow") or {}
        st_c  = st.get("color",  "#888")
        dow_c = dow.get("color", "#888")
        sig   = _signal_tag(st.get("signal"))

        elapsed = dow.get("elapsed_str")
        bars    = dow.get("bars_since")
        pending = dow.get("pending", False)
        if elapsed and bars is not None:
            pivot = (f'<span class="pivot-tag" style="background:#30363d;color:#8b949e">'
                     f'Pivot {elapsed}/{bars}b</span>')
        elif pending:
            pivot = '<span class="pivot-tag" style="background:#f0c04022;color:#f0c040">Pending</span>'
        else:
            pivot = ""

        tf_rows += (f'<div class="tf-row">'
                    f'<span class="tf-lbl">{tf["label"]}</span>'
                    f'{_badge(st.get("label","N/A"), st_c)}{sig}'
                    f'{_badge(dow.get("label","N/A"), dow_c)}'
                    f'{pivot}'
                    f'</div>')

    # チャートタブ（展開時のみ）
    tab_heads  = ""
    tab_bodies = ""
    for i, (tf, res) in enumerate(tf_r):
        tid    = f"{sid}_{tf['label']}"
        active = "active" if i == 0 else ""
        st     = res.get("st") or {}
        st_c   = st.get("color","#888")
        tab_heads  += (f'<button class="tab-btn {active}" '
                       f'onclick="switchTab(\'{sid}\',\'{tid}\',this)">'
                       f'{tf["label"]}'
                       f'<span class="tab-dot" style="background:{st_c}"></span>'
                       f'</button>')
        chart_html = chart_html_map.get(tid, "")
        tab_bodies += (f'<div class="tab-pane {active}" id="{tid}">'
                       f'{chart_html if chart_html else "<p class=no-chart>Chart not available (market closed or data error)</p>"}'
                       f'</div>')

    is_pickup = str(item.get("is_pickup", False)).lower()

    return (f'<div class="symbol-card" id="{cid}" '
            f'data-name="{sym["name"]}" data-ticker="{sym["ticker"]}" '
            f'data-cat="{sym["category"]}" data-score="{mtf["score"]}" '
            f'data-trend="{mtf["direction"]}" data-pickup="{is_pickup}">'

            # ヘッダー行（タップで折りたたみ）
            f'<div class="card-hdr" onclick="toggleCard(\'{cid}\')">'
            f'<div class="card-left">'
            f'<span class="sym-name">{sym["name"]}</span>'
            f'<span class="sym-ticker">{sym["ticker"]}</span>'
            f'<span class="sym-cat">{sym["category"]}</span>'
            f'</div>'
            f'<div class="card-right">'
            f'<span class="mtf-label" style="color:{mtf["color"]}">{mtf["label"]}</span>'
            f'{_score_bar(mtf["score"], mtf["color"])}'
            f'<span class="card-arrow" id="arr-{cid}">&#9650;</span>'
            f'</div>'
            f'</div>'

            # TFサマリー（常時表示）
            f'<div class="tf-summary-wrap" id="sum-{cid}">'
            f'{tf_rows}'
            f'</div>'

            # チャートエリア（展開時のみ表示）
            f'<div class="chart-area hidden" id="chart-{cid}">'
            f'<div class="tab-heads" id="heads_{sid}">{tab_heads}</div>'
            f'<div class="tab-content">{tab_bodies}</div>'
            f'</div>'

            f'</div>')


# ── メイン ────────────────────────────────────────────────
def generate_html(all_results, pickup_list, chart_html_map=None,
                  hot_list=None, symbol_info_map=None):
    if chart_html_map  is None: chart_html_map  = {}
    if symbol_info_map is None: symbol_info_map = {}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    refresh_meta = ""
    if OUTPUT.get("auto_refresh_minutes", 0) > 0:
        secs = OUTPUT["auto_refresh_minutes"] * 60
        refresh_meta = f'<meta http-equiv="refresh" content="{secs}">'

    pickup_tickers = {p["ticker"] for p in pickup_list}
    for item in all_results:
        item["is_pickup"] = item["symbol"]["ticker"] in pickup_tickers

    categories = list(dict.fromkeys(i["symbol"]["category"] for i in all_results))
    all_cards  = "".join(_symbol_card(i, chart_html_map) for i in all_results)
    modals     = _pickup_modals(pickup_list, symbol_info_map)
    json_cats  = _json.dumps(list(categories))

    from chart import get_lw_charts_js
    lw_js = get_lw_charts_js()

    total        = len(all_results)
    pickup_count = len(pickup_list)

    html = f'''<!DOCTYPE html>
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
    :root{{--bg:#0d1117;--bg2:#161b22;--bg3:#21262d;--border:#30363d;
          --text:#e6edf3;--text2:#8b949e;--up:#26a69a;--down:#ef5350;
          --range:#ffa726;--accent:#58a6ff;--gold:#f0c040;}}
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{background:var(--bg);color:var(--text);font-family:-apple-system,'Segoe UI',sans-serif;font-size:14px;}}

    header{{background:var(--bg2);border-bottom:1px solid var(--border);padding:11px 14px;padding-top:calc(11px + env(safe-area-inset-top,0px));
            display:flex;align-items:center;gap:10px;position:sticky;top:0;z-index:100;}}
    .htitle{{font-size:16px;font-weight:700;}}
    .hmeta{{margin-left:auto;display:flex;align-items:center;gap:10px;}}
    .hstat{{font-size:12px;color:var(--text2);}}
    .hstat span{{color:var(--gold);font-weight:700;}}
    .htime{{font-size:11px;color:var(--text2);}}

    main{{max-width:900px;margin:0 auto;padding:10px 12px calc(40px + env(safe-area-inset-bottom,0px));}}

    /* Collapsible section */
    .collapsible-section{{background:var(--bg2);border:1px solid var(--border);
      border-radius:8px;margin-bottom:10px;overflow:hidden;}}
    .sec-header{{padding:10px 14px;display:flex;align-items:center;justify-content:space-between;
      cursor:pointer;font-size:14px;font-weight:600;user-select:none;}}
    .sec-header:hover{{background:var(--bg3);}}
    .sec-body{{}}
    .sec-body.hidden{{display:none;}}
    .arrow{{font-size:10px;color:var(--text2);transition:transform .2s;}}
    .arrow.down{{transform:rotate(180deg);}}
    .src-badge{{font-size:10px;color:var(--text2);background:var(--bg3);
      padding:1px 7px;border-radius:10px;margin-left:8px;font-weight:400;}}

    /* Hot */
    .hot-tabs{{display:flex;background:var(--bg3);border-bottom:1px solid var(--border);
      padding:0 12px;gap:4px;overflow-x:auto;}}
    .hot-tab{{background:none;border:none;color:var(--text2);padding:8px 14px;cursor:pointer;
      font-size:13px;border-bottom:2px solid transparent;white-space:nowrap;}}
    .hot-tab.active{{color:var(--tc,var(--text));border-bottom-color:var(--tc,var(--accent));}}
    .hot-pane{{display:none;overflow-x:auto;}}
    .hot-pane.active{{display:block;}}
    .hot-table{{width:100%;border-collapse:collapse;font-size:13px;}}
    .hot-table th{{padding:7px 12px;text-align:left;color:var(--text2);font-size:11px;
      border-bottom:1px solid var(--border);white-space:nowrap;}}
    .hot-table td{{padding:8px 12px;border-bottom:1px solid #1a2030;vertical-align:middle;}}
    .hot-table tr:last-child td{{border-bottom:none;}}
    .hot-table tr:hover td{{background:var(--bg3);}}
    .hot-ticker{{font-weight:700;font-size:13px;display:block;}}
    .hot-name{{font-size:11px;color:var(--text2);display:block;max-width:150px;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .num{{text-align:right;white-space:nowrap;}}
    .mktcap{{color:var(--text2);}}
    .vol-badge{{display:inline-block;margin-left:4px;font-size:9px;background:#f0c04033;
      color:var(--gold);padding:1px 5px;border-radius:3px;font-weight:700;}}
    .hot-error{{padding:12px;color:var(--text2);font-size:13px;}}

    /* Pickup */
    .pickup-section{{background:var(--bg2);border:1px solid var(--border);
      border-radius:8px;padding:12px;margin-bottom:10px;}}
    .pickup-title{{font-size:14px;font-weight:700;margin-bottom:4px;}}
    .pickup-cnt{{background:var(--gold);color:#000;font-size:11px;padding:1px 8px;
      border-radius:10px;margin-left:6px;font-weight:700;}}
    .pickup-cond{{font-size:11px;color:var(--text2);font-weight:400;margin-left:8px;}}
    .pickup-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;}}
    .pickup-card{{background:var(--bg3);border-radius:6px;padding:10px 12px;
      min-width:160px;flex:1 1 160px;cursor:pointer;transition:background .15s;}}
    .pickup-card:hover{{background:#2a3140;}}
    .pc-header{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:3px;}}
    .pc-name{{font-weight:700;font-size:14px;}}
    .pc-ticker{{font-size:11px;color:var(--text2);}}
    .pc-cat{{font-size:10px;background:var(--bg);padding:1px 6px;border-radius:10px;color:var(--text2);}}
    .pc-dir{{font-size:13px;font-weight:600;margin:2px 0;}}
    .pc-meta{{font-size:11px;color:var(--text2);margin-bottom:3px;}}
    .pc-hint{{font-size:10px;color:var(--accent);margin-top:6px;text-align:right;}}
    .pickup-empty{{color:var(--text2);font-size:13px;}}
    .ev-badge{{display:inline-block;font-size:10px;padding:2px 7px;border-radius:4px;
      margin:2px 3px 2px 0;font-weight:600;}}
    .ev-badge.earn{{background:rgba(88,166,255,.15);color:#58a6ff;}}
    .ev-badge.div{{background:rgba(38,166,154,.15);color:#26a69a;}}

    /* Modal */
    .modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);
      z-index:500;align-items:flex-end;justify-content:center;}}
    .modal-overlay.open{{display:flex;}}
    .modal-box{{background:var(--bg2);border-radius:16px 16px 0 0;width:100%;
      max-width:600px;max-height:85dvh;overflow-y:auto;}}
    .modal-hdr{{padding:14px 16px;display:flex;align-items:flex-start;
      justify-content:space-between;border-bottom:1px solid var(--border);}}
    .modal-name{{font-size:17px;font-weight:700;}}
    .modal-tkr{{font-size:12px;color:var(--text2);margin-top:2px;}}
    .modal-x{{background:var(--bg3);border:none;color:var(--text2);width:28px;height:28px;
      border-radius:50%;cursor:pointer;font-size:16px;display:flex;align-items:center;
      justify-content:center;flex-shrink:0;}}
    .modal-body{{padding:14px 16px;display:flex;flex-direction:column;gap:10px;}}
    .modal-trend{{font-size:15px;font-weight:700;}}
    .modal-sub{{font-size:11px;color:var(--text2);text-transform:uppercase;
      letter-spacing:.05em;margin-top:2px;}}
    .info-table{{width:100%;border-collapse:collapse;font-size:13px;}}
    .info-table td{{padding:5px 0;border-bottom:1px solid var(--border);}}
    .info-table tr:last-child td{{border-bottom:none;}}
    .il{{color:var(--text2);width:45%;}}
    .rec-bar-wrap{{display:flex;height:7px;border-radius:4px;overflow:hidden;gap:1px;margin-bottom:5px;}}
    .rec-bar{{height:100%;}}
    .rec-labels{{display:flex;font-size:12px;gap:10px;}}
    .upg-table{{width:100%;border-collapse:collapse;font-size:12px;}}
    .upg-table td{{padding:4px 0;border-bottom:1px solid var(--border);}}
    .upg-table tr:last-child td{{border-bottom:none;}}
    .news-list{{display:flex;flex-direction:column;gap:5px;}}
    .news-item{{display:flex;flex-direction:column;gap:2px;padding:8px;
      background:var(--bg3);border-radius:6px;text-decoration:none;color:inherit;}}
    .news-item:hover{{background:#2a3140;}}
    .news-date{{font-size:10px;color:var(--text2);}}
    .news-title{{font-size:13px;line-height:1.4;}}
    .modal-no-data{{color:var(--text2);font-size:13px;}}

    /* Search */
    .search-bar{{background:var(--bg2);border:1px solid var(--border);
      border-radius:8px;padding:10px 12px;margin-bottom:10px;}}
    .sw{{position:relative;display:flex;align-items:center;margin-bottom:8px;}}
    .si{{position:absolute;left:10px;font-size:13px;pointer-events:none;}}
    #si{{width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:7px;
      color:var(--text);padding:8px 30px 8px 32px;font-size:14px;outline:none;}}
    #si:focus{{border-color:var(--accent);}}
    #si::placeholder{{color:var(--text2);}}
    #sc{{position:absolute;right:8px;background:none;border:none;color:var(--text2);
      font-size:13px;cursor:pointer;padding:4px;}}
    .fr{{display:flex;flex-wrap:wrap;gap:5px;}}
    .fg{{display:flex;flex-wrap:wrap;gap:4px;}}
    .fb{{background:var(--bg3);border:1px solid var(--border);border-radius:6px;
      color:var(--text2);padding:4px 9px;font-size:12px;cursor:pointer;white-space:nowrap;}}
    .fb.active{{background:var(--accent);border-color:var(--accent);color:#fff;}}
    .tb[data-trend="up"].active{{background:var(--up);border-color:var(--up);}}
    .tb[data-trend="down"].active{{background:var(--down);border-color:var(--down);}}
    .tb[data-trend="range"].active{{background:var(--range);border-color:var(--range);}}

    /* Symbol card */
    .symbol-card{{background:var(--bg2);border:1px solid var(--border);
      border-radius:8px;margin-bottom:8px;overflow:hidden;}}
    .symbol-card.hidden{{display:none;}}
    .symbol-card[data-pickup="true"] .card-hdr{{border-left:3px solid var(--gold);}}

    /* カードヘッダー（タップで折りたたみ） */
    .card-hdr{{padding:10px 13px;display:flex;align-items:center;gap:8px;
      cursor:pointer;user-select:none;border-bottom:1px solid var(--border);}}
    .card-hdr:hover{{background:var(--bg3);}}
    .card-left{{display:flex;align-items:center;gap:7px;flex:1;min-width:0;}}
    .card-right{{display:flex;align-items:center;gap:8px;flex-shrink:0;}}
    .sym-name{{font-weight:700;font-size:15px;}}
    .sym-ticker{{font-size:12px;color:var(--text2);}}
    .sym-cat{{font-size:11px;padding:1px 7px;border-radius:10px;
      background:var(--bg3);color:var(--text2);}}
    .mtf-label{{font-size:12px;font-weight:600;white-space:nowrap;}}
    .card-arrow{{font-size:10px;color:var(--text2);transition:transform .2s;margin-left:4px;}}
    .card-arrow.down{{transform:rotate(180deg);}}

    /* TFサマリー行 */
    .tf-summary-wrap{{padding:6px 13px;border-bottom:1px solid var(--border);}}
    .tf-row{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;
      padding:4px 0;border-bottom:1px solid #1a2030;}}
    .tf-row:last-child{{border-bottom:none;}}
    .tf-lbl{{font-size:11px;color:var(--text2);width:44px;flex-shrink:0;font-weight:600;}}

    /* チャートエリア */
    .chart-area{{}}
    .chart-area.hidden{{display:none;}}
    .tab-heads{{display:flex;background:var(--bg3);border-bottom:1px solid var(--border);
      padding:0 10px;gap:2px;overflow-x:auto;}}
    .tab-btn{{background:none;border:none;color:var(--text2);padding:7px 10px;
      cursor:pointer;font-size:12px;display:flex;align-items:center;gap:4px;
      white-space:nowrap;border-bottom:2px solid transparent;}}
    .tab-btn.active{{color:var(--text);border-bottom-color:var(--accent);}}
    .tab-dot{{width:7px;height:7px;border-radius:50%;}}
    .tab-pane{{display:none;}}.tab-pane.active{{display:block;}}
    .no-chart{{padding:20px;color:var(--text2);font-size:13px;}}

    /* Badges */
    .badge{{display:inline-block;padding:2px 7px;border-radius:3px;
      font-size:11px;font-weight:600;color:#fff;}}
    .signal-tag{{display:inline-block;padding:1px 6px;border-radius:3px;
      font-size:10px;font-weight:700;color:#fff;}}
    .pivot-tag{{display:inline-block;padding:1px 7px;border-radius:3px;
      font-size:10px;font-weight:600;margin-left:2px;}}

    /* Score bar */
    .score-bar-wrap{{display:flex;align-items:center;gap:5px;width:80px;}}
    .score-bar{{height:4px;border-radius:2px;min-width:2px;}}
    .score-num{{font-size:11px;color:var(--text2);width:22px;}}

    #no-results{{display:none;padding:30px;text-align:center;color:var(--text2);}}

    @media(max-width:600px){{
      main{{padding:8px 8px 32px;}}
      .card-left{{flex-wrap:wrap;}}
      .mktcap{{display:none;}}
      .score-bar-wrap{{width:60px;}}
    }}
  </style>
</head>
<body>
<header>
  <div class="htitle">&#128202; {OUTPUT['title']}</div>
  <div class="hmeta">
    <div class="hstat">Watch: <span>{total}</span></div>
    <div class="hstat">&#11088; <span>{pickup_count}</span></div>
    <div class="htime">&#128336; {now}</div>
  </div>
</header>
<main>
  {_hot_section(hot_list or [])}
  {_pickup_section(pickup_list, symbol_info_map)}
  {_search_bar(categories)}
  <div id="cc">{all_cards}</div>
  <div id="no-results">No symbols found</div>
</main>
{modals}
<script>
// Section collapse
function toggleSec(id){{
  var b=document.getElementById('body-'+id);
  var a=document.getElementById('arr-'+id);
  b.classList.toggle('hidden');
  a.classList.toggle('down');
}}

// Card collapse
function toggleCard(cid){{
  var sum=document.getElementById('sum-'+cid);
  var ch=document.getElementById('chart-'+cid);
  var arr=document.getElementById('arr-'+cid);
  sum.classList.toggle('hidden');
  ch.classList.toggle('hidden');
  arr.classList.toggle('down');
}}

// Hot tabs
function switchHotTab(id,btn){{
  document.querySelectorAll('.hot-tab').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.hot-pane').forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('hot-'+id).classList.add('active');
}}

// Chart tabs
function switchTab(sid,tid,btn){{
  document.querySelectorAll('#heads_'+sid+' .tab-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#chart-card_'+sid+' .tab-pane').forEach(p=>p.classList.remove('active'));
  document.getElementById(tid).classList.add('active');
}}

// Modal
function openModal(id){{var el=document.getElementById(id);if(el){{el.classList.add('open');document.body.style.overflow='hidden';}}}}
function closeModal(id){{var el=document.getElementById(id);if(el){{el.classList.remove('open');document.body.style.overflow='';}}}}
function closeModalOut(e,id){{if(e.target===e.currentTarget)closeModal(id);}}

// Search & Filter
var _cats=new Set(__CATS__),_trend='all',_sort='default',_q='';
function onSearch(v){{_q=v.trim().toLowerCase();document.getElementById('sc').style.display=v?'block':'none';applyFilter();}}
function clearSearch(){{document.getElementById('si').value='';onSearch('');}}
function togCat(btn){{var c=btn.dataset.cat;if(_cats.has(c)){{_cats.delete(c);btn.classList.remove('active');}}else{{_cats.add(c);btn.classList.add('active');}}applyFilter();}}
function togTrend(btn){{document.querySelectorAll('.tb').forEach(b=>b.classList.remove('active'));btn.classList.add('active');_trend=btn.dataset.trend;applyFilter();}}
function togSort(btn){{document.querySelectorAll('.sb').forEach(b=>b.classList.remove('active'));btn.classList.add('active');_sort=btn.dataset.sort;applyFilter();}}
function fuzzy(s,q){{s=s.toLowerCase();q=q.toLowerCase();var si=0,qi=0;while(si<s.length&&qi<q.length){{if(s[si]===q[qi])qi++;si++;}}return qi===q.length;}}
function applyFilter(){{
  var cc=document.getElementById('cc');
  var cards=Array.from(cc.querySelectorAll('.symbol-card'));
  var vis=[];
  cards.forEach(function(c){{
    var n=(c.dataset.name||'').toLowerCase(),t=(c.dataset.ticker||'').toLowerCase();
    var ok=_cats.has(c.dataset.cat)
      &&(_trend==='all'||c.dataset.trend===_trend)
      &&(_sort!=='pickup'||c.dataset.pickup==='true')
      &&(!_q||n.includes(_q)||t.includes(_q)||fuzzy(n,_q)||fuzzy(t,_q));
    c.classList.toggle('hidden',!ok);
    if(ok)vis.push(c);
  }});
  if(_sort==='score'){{vis.sort((a,b)=>parseFloat(b.dataset.score)-parseFloat(a.dataset.score));vis.forEach(c=>cc.appendChild(c));}}
  var rc=document.getElementById('rc');
  rc.textContent=(_q||_trend!=='all'||_sort==='pickup')?vis.length+' of '+cards.length+' shown':'';
  document.getElementById('no-results').style.display=vis.length===0?'block':'none';
}}
</script>
</body>
</html>'''

    return html.replace('__CATS__', json_cats)