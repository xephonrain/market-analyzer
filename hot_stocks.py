#!/usr/bin/env python3
# ============================================================
#  hot_stocks.py  - Yahoo Finance スクリーナーでホット銘柄取得
# ============================================================
import yfinance as yf


# 取得するスクリーナーと表示設定
SCREENERS = [
    {
        "id":    "most_actives",
        "label": "出来高急増",
        "icon":  "🔊",
        "color": "#58a6ff",
        "count": 10,
    },
    {
        "id":    "day_gainers",
        "label": "急騰",
        "icon":  "🔥",
        "color": "#26a69a",
        "count": 10,
    },
    {
        "id":    "day_losers",
        "label": "急落",
        "icon":  "📉",
        "color": "#ef5350",
        "count": 10,
    },
]

# quotesから取り出すフィールドマッピング
_FIELD_MAP = {
    "symbol":                       "ticker",
    "shortName":                    "name",
    "regularMarketPrice":           "price",
    "regularMarketChange":          "change",
    "regularMarketChangePercent":   "change_pct",
    "regularMarketVolume":          "volume",
    "averageDailyVolume3Month":     "avg_volume",
    "marketCap":                    "market_cap",
    "regularMarketDayHigh":         "day_high",
    "regularMarketDayLow":          "day_low",
}


def _parse_quote(q: dict) -> dict:
    """1件のquoteデータを整形"""
    out = {}
    for src, dst in _FIELD_MAP.items():
        out[dst] = q.get(src)

    # 表示用フォーマット
    price      = out.get("price") or 0
    change_pct = out.get("change_pct") or 0
    volume     = out.get("volume") or 0
    avg_vol    = out.get("avg_volume") or 0
    market_cap = out.get("market_cap") or 0

    out["price_str"]      = f"${price:,.2f}"
    out["change_pct_str"] = f"{change_pct:+.2f}%"
    out["volume_str"]     = _fmt_number(volume)
    out["avg_vol_str"]    = _fmt_number(avg_vol)
    out["market_cap_str"] = _fmt_market_cap(market_cap)
    out["vol_ratio"]      = round(volume / avg_vol, 1) if avg_vol > 0 else None
    out["positive"]       = change_pct >= 0

    return out


def _fmt_number(n) -> str:
    if n is None:
        return "-"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def _fmt_market_cap(n) -> str:
    if n is None or n == 0:
        return "-"
    if n >= 1_000_000_000_000:
        return f"${n/1_000_000_000_000:.1f}T"
    if n >= 1_000_000_000:
        return f"${n/1_000_000_000:.0f}B"
    if n >= 1_000_000:
        return f"${n/1_000_000:.0f}M"
    return f"${n:,}"


def fetch_hot_stocks() -> list[dict]:
    """
    全スクリーナーを実行してホット銘柄リストを返す

    Returns:
        [
          {
            "id": "most_actives",
            "label": "出来高急増",
            "icon": "🔊",
            "color": "#58a6ff",
            "stocks": [ {ticker, name, price_str, ...}, ... ],
            "error": None or str,
          },
          ...
        ]
    """
    results = []

    for sc in SCREENERS:
        entry = {
            "id":     sc["id"],
            "label":  sc["label"],
            "icon":   sc["icon"],
            "color":  sc["color"],
            "stocks": [],
            "error":  None,
        }

        try:
            raw = yf.screen(sc["id"], count=sc["count"])
            quotes = raw.get("quotes", [])
            entry["stocks"] = [_parse_quote(q) for q in quotes]
            print(f"  [{sc['label']}] {len(entry['stocks'])}件取得")
        except Exception as e:
            entry["error"] = str(e)
            print(f"  [{sc['label']}] エラー: {e}")

        results.append(entry)

    return results
