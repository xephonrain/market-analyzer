#!/usr/bin/env python3
# ============================================================
#  symbol_info.py  - ピックアップ銘柄の追加情報取得
#  yfinance で取れる情報のみ（APIキー不要）
# ============================================================
import yfinance as yf
from datetime import datetime, timezone
import traceback


def _safe(fn):
    """例外を握り潰してNoneを返すラッパー"""
    try:
        return fn()
    except Exception:
        return None


def _fmt_date(ts):
    """Unixタイムスタンプ or datetime → 'YYYY-MM-DD' 文字列"""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')
        if hasattr(ts, 'strftime'):
            return ts.strftime('%Y-%m-%d')
        return str(ts)[:10]
    except Exception:
        return None


def _fmt_large(n):
    """大きな数値を T/B/M 表記に"""
    if n is None:
        return None
    try:
        n = float(n)
        if n >= 1e12: return f"${n/1e12:.1f}T"
        if n >= 1e9:  return f"${n/1e9:.1f}B"
        if n >= 1e6:  return f"${n/1e6:.1f}M"
        return f"${n:,.0f}"
    except Exception:
        return None


def fetch_symbol_info(ticker: str) -> dict:
    """
    1銘柄の追加情報を取得して返す

    Returns:
    {
      "ticker": str,
      "name": str,
      "sector": str,
      "industry": str,
      "market_cap": str,
      "week52_high": float,
      "week52_low": float,
      "current_price": float,
      "pct_from_high": float,    # 52週高値からの乖離率
      "target_price": float,     # アナリスト平均目標株価
      "analyst_count": int,
      "recommendation": str,     # "buy" / "hold" / "sell"
      "earnings_date": str,      # 次回決算日
      "ex_dividend_date": str,   # 配当落ち日
      "dividend_date": str,      # 配当支払日
      "rec_buy": int,            # Buy推奨件数
      "rec_hold": int,
      "rec_sell": int,
      "upgrades": [...],         # 直近レーティング変更
      "news": [...],             # 直近ニュース
      "error": None or str,
    }
    """
    result = {
        "ticker": ticker,
        "name": None, "sector": None, "industry": None,
        "market_cap": None, "week52_high": None, "week52_low": None,
        "current_price": None, "pct_from_high": None,
        "target_price": None, "analyst_count": None, "recommendation": None,
        "earnings_date": None, "ex_dividend_date": None, "dividend_date": None,
        "rec_buy": None, "rec_hold": None, "rec_sell": None,
        "short_ratio": None, "short_float_pct": None,
        "held_pct_insiders": None, "held_pct_institutions": None,
        "float_shares": None, "shares_short": None,
        "upgrades": [], "news": [],
        "error": None,
    }

    try:
        t = yf.Ticker(ticker)

        # ── info ─────────────────────────────────────────
        info = _safe(lambda: t.info) or {}

        result["name"]         = info.get("longName") or info.get("shortName")
        result["sector"]       = info.get("sector")
        result["industry"]     = info.get("industry")
        result["market_cap"]   = _fmt_large(info.get("marketCap"))
        result["week52_high"]  = info.get("fiftyTwoWeekHigh")
        result["week52_low"]   = info.get("fiftyTwoWeekLow")
        result["current_price"]= info.get("currentPrice") or info.get("regularMarketPrice")
        result["target_price"]         = info.get("targetMeanPrice")
        result["analyst_count"]         = info.get("numberOfAnalystOpinions")
        result["recommendation"]        = info.get("recommendationKey")
        # 需給情報
        result["short_ratio"]           = info.get("shortRatio")
        result["short_float_pct"]       = info.get("shortPercentOfFloat")
        result["held_pct_insiders"]     = info.get("heldPercentInsiders")
        result["held_pct_institutions"] = info.get("heldPercentInstitutions")
        result["float_shares"]          = _fmt_large(info.get("floatShares"))
        result["shares_short"]          = _fmt_large(info.get("sharesShort"))

        # 52週高値からの乖離率
        if result["current_price"] and result["week52_high"]:
            pct = (result["current_price"] - result["week52_high"]) / result["week52_high"] * 100
            result["pct_from_high"] = round(pct, 1)

        # ── calendar（決算日・配当日） ────────────────────
        cal = _safe(lambda: t.calendar) or {}
        if isinstance(cal, dict):
            # 決算日
            ed = cal.get("Earnings Date")
            if ed is None:
                ed = cal.get("earningsDate")
            if isinstance(ed, list) and len(ed) > 0:
                result["earnings_date"] = _fmt_date(ed[0])
            elif ed is not None:
                result["earnings_date"] = _fmt_date(ed)

            # 配当落ち日
            result["ex_dividend_date"] = _fmt_date(
                cal.get("Ex-Dividend Date") or cal.get("exDividendDate"))
            # 配当支払日
            result["dividend_date"] = _fmt_date(
                cal.get("Dividend Date") or cal.get("dividendDate"))

        # infoからも決算日を補完
        if not result["earnings_date"]:
            ts = info.get("earningsTimestampStart") or info.get("earningsTimestamp")
            if ts:
                result["earnings_date"] = _fmt_date(ts)

        if not result["ex_dividend_date"]:
            result["ex_dividend_date"] = _fmt_date(info.get("exDividendDate"))

        # ── recommendations_summary ───────────────────────
        rec_df = _safe(lambda: t.recommendations_summary)
        if rec_df is not None and not rec_df.empty:
            # 直近1期のデータ
            row = rec_df.iloc[0]
            result["rec_buy"]  = int(row.get("strongBuy", 0) + row.get("buy", 0))
            result["rec_hold"] = int(row.get("hold", 0))
            result["rec_sell"] = int(row.get("sell", 0) + row.get("strongSell", 0))

        # ── upgrades_downgrades（直近3件） ────────────────
        upg = _safe(lambda: t.upgrades_downgrades)
        if upg is not None and not upg.empty:
            upg = upg.head(3)
            for _, row in upg.iterrows():
                result["upgrades"].append({
                    "date":   str(row.name)[:10] if hasattr(row.name, '__str__') else "",
                    "firm":   row.get("Firm", ""),
                    "action": row.get("Action", ""),
                    "from":   row.get("FromGrade", ""),
                    "to":     row.get("ToGrade", ""),
                })

        # ── news（直近3件） ───────────────────────────────
        news = _safe(lambda: t.news) or []
        for item in news[:3]:
            content = item.get("content", {})
            title   = content.get("title") or item.get("title", "")
            link    = (content.get("canonicalUrl", {}) or {}).get("url") or \
                      (item.get("link") or "")
            pub     = content.get("pubDate") or item.get("providerPublishTime")
            result["news"].append({
                "title": title[:80] if title else "",
                "link":  link,
                "date":  _fmt_date(pub) if pub else "",
            })

        print(f"  [info] {ticker}: {result['name']} / "
              f"earnings={result['earnings_date']} / "
              f"rec={result['recommendation']}")

    except Exception as e:
        result["error"] = str(e)
        print(f"  [WARNING] {ticker} info取得失敗: {e}")

    return result


def fetch_all_symbol_info(tickers: list[str]) -> dict[str, dict]:
    """複数ティッカーの情報を一括取得"""
    results = {}
    for ticker in tickers:
        results[ticker] = fetch_symbol_info(ticker)
    return results
