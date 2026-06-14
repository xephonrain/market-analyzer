#!/usr/bin/env python3
# ============================================================
#  report.py  - HTMLレポート生成
#  Phase 3: 検索・フィルター・ホット銘柄セクション追加
# ============================================================
from datetime import datetime
from collections import defaultdict
from config import OUTPUT, PICKUP_CONDITIONS


# ── 小部品 ────────────────────────────────────────────────
def _badge(label, color):
    return f'<span class="badge" style="background:{color}">{label}</span>'

def _score_bar(score, color):
    return (f'<div class="score-bar-wrap">'
            f'<div class="score-bar" style="width:{score}%;background:{color}"></div>'
            f'<span class="score-num">{score:.0f}</span></div>')

def _signal_tag(signal):
    if not signal:
        return ""
    sc = "#26a69a" if signal == "BUY" else "#ef5350"
    return f'<span class="signal-tag" style="background:{sc}">{signal}</span>'


# ── ホット銘柄セクション ──────────────────────────────────
def _hot_section(hot_list):
    if not hot_list:
        return ""

    tabs_head = ""
    tabs_body = ""
    for i, sc in enumerate(hot_list):
        active = "active" if i == 0 else ""
        tabs_head += (f'<button class="hot-tab {active}" '
                      f'style="--tab-color:{sc["color"]}" '
                      f'onclick="switchHotTab(\'{sc["id"]}\',this)">'
                      f'{sc["icon"]} {sc["label"]}</button>')

        if sc.get("error"):
            body = f'<div class="hot-error">取得エラー: {sc["error"]}</div>'
        elif not sc.get("stocks"):
            body = '<div class="hot-error">データなし</div>'
        else:
            rows = ""
            for s in sc["stocks"]:
                pct   = s.get("change_pct_str", "-")
                pos   = s.get("positive", True)
                pct_c = "#26a69a" if pos else "#ef5350"
                arrow = "▲" if pos else "▼"
                vol_ratio = s.get("vol_ratio")
                vol_badge = (f'<span class="vol-badge">{vol_ratio}x</span>'
                             if vol_ratio and vol_ratio >= 2 else "")
                rows += (f'<tr data-ticker="{s.get("ticker","")}" '
                         f'data-name="{s.get("name","")}">'
                         f'<td><span class="hot-ticker">{s.get("ticker","")}</span>'
                         f'<span class="hot-name">{s.get("name","")}</span></td>'
                         f'<td class="num">{s.get("price_str","-")}</td>'
                         f'<td class="num" style="color:{pct_c}">{arrow}{pct}</td>'
                         f'<td class="num">{s.get("volume_str","-")}{vol_badge}</td>'
                         f'<td class="num mktcap">{s.get("market_cap_str","-")}</td>'
                         f'</tr>')
            body = (f'<table class="hot-table">'
                    f'<thead><tr><th>銘柄</th><th>価格</th>'
                    f'<th>騰落率</th><th>出来高</th><th>時価総額</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>')

        tabs_body += (f'<div class="hot-pane {active}" id="hot-{sc["id"]}">'
                      f'{body}</div>')

    return f'''
<section class="hot-section">
  <div class="section-title">📡 マーケット動向 <span class="hot-src">Yahoo Finance</span></div>
  <div class="hot-tabs">{tabs_head}</div>
  <div class="hot-content">{tabs_body}</div>
</section>'''


# ── 検索・フィルターバー ──────────────────────────────────
def _search_bar(categories):
    cat_opts = "".join(
        f'<button class="filter-btn active" data-cat="{c}" onclick="toggleCat(this)">{c}</button>'
        for c in categories
    )
    return f'''
<div class="search-bar" id="search-bar">
  <div class="search-row">
    <div class="search-wrap">
      <span class="search-icon">🔍</span>
      <input id="search-input" type="search" placeholder="銘柄名 / ティッカーで検索..."
             oninput="onSearch(this.value)" autocapitalize="none" autocorrect="off">
      <button class="search-clear" id="search-clear" onclick="clearSearch()" style="display:none">✕</button>
    </div>
  </div>
  <div class="filter-row">
    <div class="filter-group">
      <button class="filter-btn trend-btn active" data-trend="all"   onclick="toggleTrend(this)">全て</button>
      <button class="filter-btn trend-btn"        data-trend="up"    onclick="toggleTrend(this)">↑ 上昇</button>
      <button class="filter-btn trend-btn"        data-trend="down"  onclick="toggleTrend(this)">↓ 下降</button>
      <button class="filter-btn trend-btn"        data-trend="range" onclick="toggleTrend(this)">→ レンジ</button>
    </div>
    <div class="filter-group cat-group">
      {cat_opts}
    </div>
    <div class="filter-group">
      <button class="filter-btn sort-btn active" data-sort="default" onclick="toggleSort(this)">デフォルト</button>
      <button class="filter-btn sort-btn"        data-sort="score"   onclick="toggleSort(this)">スコア順</button>
      <button class="filter-btn sort-btn"        data-sort="pickup"  onclick="toggleSort(this)">⭐のみ</button>
    </div>
  </div>
  <div class="search-result-count" id="result-count"></div>
</div>'''


# ── ピックアップセクション ────────────────────────────────
def _pickup_section(pickup_list):
    cond = PICKUP_CONDITIONS
    desc = (f"MTFスコア ≥ {cond['mtf_score_threshold']}pt ／ "
            f"TF一致 ≥ {cond['min_tf_agreement']}本 ／ "
            f"ダウ理論トレンド確認 ／ ST方向一致")

    if not pickup_list:
        cards = '<div class="pickup-empty">条件に合致するシンボルなし</div>'
    else:
        cards = ""
        for p in pickup_list:
            arrow = "▲" if p["direction"] == "up" else "▼"
            cards += (f'<div class="pickup-card" style="border-left:4px solid {p["color"]}">'
                      f'<div class="pickup-header">'
                      f'<span class="pickup-name">{p["name"]}</span>'
                      f'<span class="pickup-ticker">{p["ticker"]}</span>'
                      f'<span class="pickup-cat">{p["category"]}</span></div>'
                      f'<div class="pickup-dir" style="color:{p["color"]}">{arrow} {p["label"]}</div>'
                      f'<div class="pickup-meta">TF一致: {p["agree"]}本</div>'
                      f'{_score_bar(p["score"], p["color"])}</div>')
        cards = f'<div class="pickup-grid">{cards}</div>'

    return f'''
<section class="pickup-section">
  <h2>⭐ ピックアップ <span class="pickup-count">{len(pickup_list)}件</span></h2>
  <div class="pickup-cond">{desc}</div>
  {cards}
</section>'''


# ── シンボルカード ────────────────────────────────────────
def _symbol_card(item, chart_html_map):
    sym    = item["symbol"]
    tf_res = item["tf_results"]
    mtf    = item["mtf_score"]
    sid    = sym["ticker"].replace("=","").replace("^","").replace(".","")

    # ダウ理論(日足)のtrendを取り出す
    daily = next((r for tf, r in tf_res if tf["label"] == "日足"), None)
    dow_trend = "range"
    if daily and daily.get("dow"):
        dow_trend = daily["dow"].get("trend", "range")

    tab_heads  = ""
    tab_bodies = ""
    for i, (tf, res) in enumerate(tf_res):
        tid    = f"{sid}_{tf['label']}"
        active = "active" if i == 0 else ""
        st     = res.get("st")  or {}
        dow    = res.get("dow") or {}
        st_c   = st.get("color",  "#888")
        dow_c  = dow.get("color", "#888")
        sig    = _signal_tag(st.get("signal"))

        tab_heads += (f'<button class="tab-btn {active}" '
                      f'onclick="switchTab(\'{sid}\',\'{tid}\',this)">'
                      f'{tf["label"]}'
                      f'<span class="tab-dot" style="background:{st_c}"></span></button>')

        chart_html = chart_html_map.get(tid, "<p style='color:#888;padding:20px'>チャートなし</p>")
        summary = (f'<div class="tf-summary">'
                   f'<span class="tf-label-sm">{tf["label"]}</span>'
                   f'{_badge(st.get("label","N/A"), st_c)}{sig}'
                   f'{_badge(dow.get("label","N/A"), dow_c)}'
                   f'<span class="dow-desc-sm">{dow.get("description","")}</span></div>')

        tab_bodies += (f'<div class="tab-pane {active}" id="{tid}">'
                       f'{summary}<div class="chart-wrap">{chart_html}</div></div>')

    return (f'<div class="symbol-card" id="card_{sid}" '
            f'data-name="{sym["name"]}" data-ticker="{sym["ticker"]}" '
            f'data-cat="{sym["category"]}" data-score="{mtf["score"]}" '
            f'data-trend="{mtf["direction"]}" '
            f'data-pickup="{str(item.get("is_pickup", False)).lower()}">'
            f'<div class="card-header">'
            f'<div class="card-title">'
            f'<span class="sym-name">{sym["name"]}</span>'
            f'<span class="sym-ticker">{sym["ticker"]}</span>'
            f'<span class="sym-cat">{sym["category"]}</span></div>'
            f'<div class="card-mtf">'
            f'<span class="mtf-label" style="color:{mtf["color"]}">{mtf["label"]}</span>'
            f'{_score_bar(mtf["score"], mtf["color"])}</div></div>'
            f'<div class="card-tabs">'
            f'<div class="tab-heads" id="heads_{sid}">{tab_heads}</div>'
            f'<div class="tab-content">{tab_bodies}</div></div></div>')


# ── メイン生成関数 ────────────────────────────────────────
def generate_html(all_results, pickup_list, chart_html_map=None, hot_list=None):
    if chart_html_map is None:
        chart_html_map = {}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    refresh_meta = ""
    if OUTPUT.get("auto_refresh_minutes", 0) > 0:
        secs = OUTPUT["auto_refresh_minutes"] * 60
        refresh_meta = f'<meta http-equiv="refresh" content="{secs}">'

    # ピックアップ銘柄のtickerセット
    pickup_tickers = {p["ticker"] for p in pickup_list}
    for item in all_results:
        item["is_pickup"] = item["symbol"]["ticker"] in pickup_tickers

    # カテゴリ収集 & カード生成（フラットに並べる）
    categories = list(dict.fromkeys(i["symbol"]["category"] for i in all_results))
    all_cards  = "".join(_symbol_card(i, chart_html_map) for i in all_results)

    from chart import get_lw_charts_js
    lw_js = get_lw_charts_js()

    total        = len(all_results)
    pickup_count = len(pickup_list)

    import json as _json
    json_cats_str = _json.dumps(list(categories))
    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  {refresh_meta}
  <title>{OUTPUT['title']}</title>
  <script>{lw_js}</script>
  <style>
    :root {{
      --bg:#0d1117; --bg2:#161b22; --bg3:#21262d;
      --border:#30363d; --text:#e6edf3; --text2:#8b949e;
      --up:#26a69a; --down:#ef5350; --range:#ffa726;
      --accent:#58a6ff; --gold:#f0c040;
    }}
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',-apple-system,sans-serif;font-size:14px;}}

    /* ── ヘッダー ── */
    header{{background:var(--bg2);border-bottom:1px solid var(--border);
            padding:12px 16px;display:flex;align-items:center;gap:10px;
            position:sticky;top:0;z-index:100;}}
    .header-title{{font-size:16px;font-weight:700;}}
    .header-meta{{margin-left:auto;display:flex;align-items:center;gap:12px;flex-wrap:wrap;}}
    .header-stat{{font-size:12px;color:var(--text2);}}
    .header-stat span{{color:var(--gold);font-weight:700;}}
    .update-time{{font-size:11px;color:var(--text2);}}

    /* ── メイン ── */
    main{{max-width:1200px;margin:0 auto;padding:12px 16px 40px;}}

    /* ── ホット銘柄 ── */
    .hot-section{{background:var(--bg2);border:1px solid var(--border);
                  border-radius:8px;margin-bottom:16px;overflow:hidden;}}
    .section-title{{padding:12px 16px 8px;font-size:14px;font-weight:700;
                    display:flex;align-items:center;gap:8px;}}
    .hot-src{{font-size:10px;color:var(--text2);background:var(--bg3);
              padding:1px 7px;border-radius:10px;font-weight:400;}}
    .hot-tabs{{display:flex;border-bottom:1px solid var(--border);
               background:var(--bg3);padding:0 12px;gap:4px;overflow-x:auto;}}
    .hot-tab{{background:none;border:none;color:var(--text2);padding:8px 14px;
              cursor:pointer;font-size:13px;border-bottom:2px solid transparent;
              white-space:nowrap;transition:all .15s;}}
    .hot-tab.active{{color:var(--tab-color,var(--text));border-bottom-color:var(--tab-color,var(--accent));}}
    .hot-content{{padding:0;}}
    .hot-pane{{display:none;overflow-x:auto;}}
    .hot-pane.active{{display:block;}}
    .hot-table{{width:100%;border-collapse:collapse;font-size:13px;}}
    .hot-table th{{padding:8px 12px;text-align:left;color:var(--text2);
                   font-size:11px;font-weight:500;border-bottom:1px solid var(--border);
                   white-space:nowrap;}}
    .hot-table td{{padding:9px 12px;border-bottom:1px solid #1a2030;vertical-align:middle;}}
    .hot-table tr:last-child td{{border-bottom:none;}}
    .hot-table tr:hover td{{background:var(--bg3);}}
    .hot-ticker{{font-weight:700;font-size:13px;display:block;}}
    .hot-name{{font-size:11px;color:var(--text2);display:block;
               white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:160px;}}
    .num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}}
    .mktcap{{color:var(--text2);}}
    .vol-badge{{display:inline-block;margin-left:5px;font-size:9px;
                background:#f0c04033;color:var(--gold);padding:1px 5px;
                border-radius:3px;font-weight:700;}}
    .hot-error{{padding:16px;color:var(--text2);font-size:13px;}}

    /* ── 検索バー ── */
    .search-bar{{background:var(--bg2);border:1px solid var(--border);
                 border-radius:8px;padding:12px 14px;margin-bottom:14px;}}
    .search-row{{margin-bottom:10px;}}
    .search-wrap{{position:relative;display:flex;align-items:center;}}
    .search-icon{{position:absolute;left:10px;font-size:14px;pointer-events:none;}}
    #search-input{{width:100%;background:var(--bg3);border:1px solid var(--border);
                   border-radius:7px;color:var(--text);padding:9px 32px 9px 34px;
                   font-size:14px;outline:none;transition:border-color .15s;}}
    #search-input:focus{{border-color:var(--accent);}}
    #search-input::placeholder{{color:var(--text2);}}
    .search-clear{{position:absolute;right:8px;background:none;border:none;
                   color:var(--text2);font-size:14px;cursor:pointer;padding:4px;}}
    .filter-row{{display:flex;flex-wrap:wrap;gap:6px;}}
    .filter-group{{display:flex;flex-wrap:wrap;gap:4px;}}
    .filter-group + .filter-group::before{{content:'';width:1px;background:var(--border);
                                           margin:0 4px;align-self:stretch;}}
    .filter-btn{{background:var(--bg3);border:1px solid var(--border);
                 border-radius:6px;color:var(--text2);padding:4px 10px;
                 font-size:12px;cursor:pointer;transition:all .15s;white-space:nowrap;}}
    .filter-btn.active{{background:var(--accent);border-color:var(--accent);color:#fff;}}
    .filter-btn[data-trend="up"].active{{background:var(--up);border-color:var(--up);}}
    .filter-btn[data-trend="down"].active{{background:var(--down);border-color:var(--down);}}
    .filter-btn[data-trend="range"].active{{background:var(--range);border-color:var(--range);}}
    .search-result-count{{font-size:11px;color:var(--text2);margin-top:8px;min-height:16px;}}

    /* ── ピックアップ ── */
    .pickup-section{{background:var(--bg2);border:1px solid var(--border);
                     border-radius:8px;padding:14px;margin-bottom:14px;}}
    .pickup-section h2{{font-size:14px;margin-bottom:5px;}}
    .pickup-count{{background:var(--gold);color:#000;font-size:11px;
                   padding:1px 8px;border-radius:10px;margin-left:6px;font-weight:700;}}
    .pickup-cond{{font-size:11px;color:var(--text2);margin-bottom:10px;}}
    .pickup-grid{{display:flex;flex-wrap:wrap;gap:8px;}}
    .pickup-card{{background:var(--bg3);border-radius:6px;padding:10px 13px;
                  min-width:180px;flex:1 1 180px;}}
    .pickup-header{{display:flex;align-items:center;gap:6px;margin-bottom:3px;flex-wrap:wrap;}}
    .pickup-name{{font-weight:700;font-size:14px;}}
    .pickup-ticker{{font-size:11px;color:var(--text2);}}
    .pickup-cat{{font-size:10px;background:var(--bg);padding:1px 6px;
                 border-radius:10px;color:var(--text2);}}
    .pickup-dir{{font-size:13px;font-weight:600;margin:2px 0;}}
    .pickup-meta{{font-size:11px;color:var(--text2);margin-bottom:4px;}}
    .pickup-empty{{color:var(--text2);font-size:13px;}}

    /* ── カード ── */
    .symbol-card{{background:var(--bg2);border:1px solid var(--border);
                  border-radius:8px;margin-bottom:10px;overflow:hidden;
                  transition:opacity .2s;}}
    .symbol-card.hidden{{display:none;}}
    .symbol-card.dimmed{{opacity:.35;}}
    .symbol-card[data-pickup="true"] .card-header{{border-left:3px solid var(--gold);}}
    .card-header{{padding:10px 14px;display:flex;align-items:center;gap:10px;
                  flex-wrap:wrap;border-bottom:1px solid var(--border);}}
    .card-title{{display:flex;align-items:center;gap:8px;flex:1;}}
    .sym-name{{font-weight:700;font-size:15px;}}
    .sym-ticker{{font-size:12px;color:var(--text2);}}
    .sym-cat{{font-size:11px;padding:1px 7px;border-radius:10px;
              background:var(--bg3);color:var(--text2);}}
    .card-mtf{{display:flex;align-items:center;gap:8px;}}
    .mtf-label{{font-size:13px;font-weight:600;white-space:nowrap;}}

    /* スコアバー */
    .score-bar-wrap{{display:flex;align-items:center;gap:5px;width:100px;}}
    .score-bar{{height:5px;border-radius:3px;min-width:2px;}}
    .score-num{{font-size:11px;color:var(--text2);width:24px;}}

    /* タブ */
    .tab-heads{{display:flex;background:var(--bg3);border-bottom:1px solid var(--border);
                padding:0 10px;gap:2px;overflow-x:auto;}}
    .tab-btn{{background:none;border:none;color:var(--text2);padding:7px 10px;
              cursor:pointer;font-size:12px;display:flex;align-items:center;gap:4px;
              white-space:nowrap;border-bottom:2px solid transparent;transition:all .15s;}}
    .tab-btn:hover{{color:var(--text);}}
    .tab-btn.active{{color:var(--text);border-bottom-color:var(--accent);}}
    .tab-dot{{width:7px;height:7px;border-radius:50%;}}
    .tab-pane{{display:none;}}
    .tab-pane.active{{display:block;}}
    .tf-summary{{padding:7px 12px;display:flex;align-items:center;gap:7px;
                 flex-wrap:wrap;border-bottom:1px solid var(--border);background:var(--bg3);}}
    .tf-label-sm{{font-size:11px;color:var(--text2);width:34px;}}
    .dow-desc-sm{{font-size:11px;color:var(--text2);}}
    .badge{{display:inline-block;padding:2px 7px;border-radius:3px;
            font-size:11px;font-weight:600;color:#fff;}}
    .signal-tag{{display:inline-block;padding:1px 6px;border-radius:3px;
                 font-size:10px;font-weight:700;color:#fff;}}
    .chart-wrap{{padding:4px;}}

    /* no-results */
    #no-results{{display:none;padding:32px;text-align:center;color:var(--text2);font-size:14px;}}

    @media(max-width:600px){{
      main{{padding:8px 10px 32px;}}
      .card-header{{flex-direction:column;align-items:flex-start;}}
      .score-bar-wrap{{width:80px;}}
      .mktcap{{display:none;}}
    }}
  </style>
</head>
<body>
<header>
  <div class="header-title">📊 {OUTPUT['title']}</div>
  <div class="header-meta">
    <div class="header-stat">監視: <span>{total}</span>銘柄</div>
    <div class="header-stat">⭐ <span>{pickup_count}</span>件</div>
    <div class="update-time">🕐 {now}</div>
  </div>
</header>
<main>
  {_hot_section(hot_list or [])}
  {_pickup_section(pickup_list)}
  {_search_bar(categories)}
  <div id="cards-container">{all_cards}</div>
  <div id="no-results">🔍 該当する銘柄が見つかりません</div>
</main>
<script>
// ════════════════════════════════════════
//  チャートタブ切り替え
// ════════════════════════════════════════
function switchTab(sid, tid, btn) {{
  document.querySelectorAll('#heads_' + sid + ' .tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#card_' + sid + ' .tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById(tid).classList.add('active');
}}

function switchHotTab(id, btn) {{
  document.querySelectorAll('.hot-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.hot-pane').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('hot-' + id).classList.add('active');
}}

// ════════════════════════════════════════
//  検索・フィルター
// ════════════════════════════════════════
var _activeCats   = new Set(__JSON_CATS__);
var _activeTrend  = 'all';
var _activeSort   = 'default';
var _searchQuery  = '';

function onSearch(val) {{
  _searchQuery = val.trim().toLowerCase();
  document.getElementById('search-clear').style.display = val ? 'block' : 'none';
  applyFilter();
}}

function clearSearch() {{
  document.getElementById('search-input').value = '';
  onSearch('');
}}

function toggleCat(btn) {{
  var cat = btn.dataset.cat;
  if (_activeCats.has(cat)) {{ _activeCats.delete(cat); btn.classList.remove('active'); }}
  else                       {{ _activeCats.add(cat);    btn.classList.add('active');    }}
  applyFilter();
}}

function toggleTrend(btn) {{
  document.querySelectorAll('.trend-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _activeTrend = btn.dataset.trend;
  applyFilter();
}}

function toggleSort(btn) {{
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _activeSort = btn.dataset.sort;
  applyFilter();
}}

// fuzzy検索: クエリの各文字が順番通りに含まれるか
function fuzzyMatch(str, query) {{
  var si = 0, qi = 0;
  str   = str.toLowerCase();
  query = query.toLowerCase();
  while (si < str.length && qi < query.length) {{
    if (str[si] === query[qi]) qi++;
    si++;
  }}
  return qi === query.length;
}}

function matchSearch(card) {{
  if (!_searchQuery) return true;
  var name   = (card.dataset.name   || '').toLowerCase();
  var ticker = (card.dataset.ticker || '').toLowerCase();
  // 部分一致
  if (name.includes(_searchQuery) || ticker.includes(_searchQuery)) return true;
  // fuzzy
  if (fuzzyMatch(name, _searchQuery) || fuzzyMatch(ticker, _searchQuery)) return true;
  return false;
}}

function applyFilter() {{
  var container = document.getElementById('cards-container');
  var cards = Array.from(container.querySelectorAll('.symbol-card'));

  // フィルタリング
  var visible = [];
  cards.forEach(function(card) {{
    var cat     = card.dataset.cat;
    var trend   = card.dataset.trend;
    var pickup  = card.dataset.pickup === 'true';
    var catOk   = _activeCats.has(cat);
    var trendOk = _activeTrend === 'all' || trend === _activeTrend;
    var pickupOk= _activeSort !== 'pickup' || pickup;
    var searchOk= matchSearch(card);
    var show    = catOk && trendOk && pickupOk && searchOk;
    card.classList.toggle('hidden', !show);
    if (show) visible.push(card);
  }});

  // ソート
  if (_activeSort === 'score') {{
    visible.sort(function(a, b) {{
      return parseFloat(b.dataset.score) - parseFloat(a.dataset.score);
    }});
    visible.forEach(function(c) {{ container.appendChild(c); }});
  }}

  // 結果数表示
  var cnt = document.getElementById('result-count');
  if (_searchQuery || _activeTrend !== 'all' || _activeSort === 'pickup') {{
    cnt.textContent = visible.length + '件 表示中 / 全' + cards.length + '件';
  }} else {{
    cnt.textContent = '';
  }}

  document.getElementById('no-results').style.display = visible.length === 0 ? 'block' : 'none';
}}
</script>
</body>
</html>'''.replace('__JSON_CATS__', json_cats_str)
