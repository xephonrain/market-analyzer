#!/usr/bin/env python3
# ============================================================
#  ai_analysis.py  - Gemini APIによる銘柄分析コメント生成
# ============================================================
import os
import json
import urllib.request
import urllib.error


GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


def _build_prompt(symbol: dict, tf_results: list, mtf: dict,
                  entry_points: list, price_info: dict) -> str:
    """Geminiに投げるプロンプトを構築"""

    # TF別サマリー
    tf_lines = []
    for tf, res in tf_results:
        st  = res.get("st", {})
        dow = res.get("dow", {})
        elapsed = dow.get("elapsed_str", "")
        bars    = dow.get("bars_since", "")
        elapsed_str = f"（{elapsed}/{bars}本前）" if elapsed and bars else ""
        tf_lines.append(
            f"  {tf['label']}: ST={st.get('label','N/A')} / "
            f"ダウ={dow.get('label','N/A')}{elapsed_str}"
        )

    # エントリーポイント
    ep_lines = []
    for ep in entry_points[:2]:  # 最大2件
        rr_str = f" RR={ep['rr']}" if ep.get("rr") else ""
        ep_lines.append(
            f"  [{ep['type']}]{ep['stars']} {ep['signal']} "
            f"Entry={ep.get('entry_price')} "
            f"SL={ep.get('sl_price')} "
            f"TP={ep.get('tp_price')}{rr_str}"
            f" ({ep['desc']})"
        )

    # 価格情報
    price_lines = []
    if price_info.get("current"):
        price_lines.append(f"  現在値: {price_info['current']}")
    if price_info.get("swing_high"):
        price_lines.append(f"  直近高値: {price_info['swing_high']} "
                           f"({price_info.get('pct_from_high',''):+.1f}%)")
    if price_info.get("swing_low"):
        price_lines.append(f"  直近安値: {price_info['swing_low']} "
                           f"({price_info.get('pct_from_low',''):+.1f}%)")
    if price_info.get("range_position") is not None:
        price_lines.append(f"  レンジ位置: {price_info['range_position']:.0f}%")

    # モメンタム情報
    mom_lines = []
    for tf, res in tf_results:
        mom = res.get("momentum") or {}
        if mom.get("ratio") is not None:
            mom_lines.append(
                f"  {tf['label']}: {mom.get('label','')}"
                f"（前{mom.get('before_bars',10)}本比）"
            )

    prompt = f"""あなたはFXと株式のプロトレーダーです。
以下のテクニカル分析データをもとに、今すぐトレード判断に使える実践的な分析コメントを日本語で書いてください。

銘柄: {symbol['name']} ({symbol['ticker']})
MTFスコア: {mtf['label']}

【マルチタイムフレーム分析】
{chr(10).join(tf_lines)}

【価格情報】
{chr(10).join(price_lines) if price_lines else '  データなし'}

【モメンタム（ブレイク強度）】
{chr(10).join(mom_lines) if mom_lines else '  データなし'}

【エントリーポイント候補】
{chr(10).join(ep_lines) if ep_lines else '  なし'}

以下の構成で出力してください（各項目1〜2文、各項目1〜2文）:

📌 状況: 現在のトレンド状況を一言で
🎯 根拠: エントリー根拠（どのTFが揃っているか、モメンタムはどうか）
⚠️ 注意: リスク・注意すべき点（逆行シグナル・高値圏・安値圏など）
📈 シナリオ: 上昇継続 or 下降継続した場合の次の目標と、崩れた場合の撤退ライン

条件:
- 前置き不要（「はい」「承知」等は書かない）
- 数値は具体的に（価格情報があれば必ず使う）
- 断定ではなく「〜が有効」「〜に注意」等の表現
- 絵文字はそのまま使う
"""
    return prompt


def generate_ai_comment(symbol: dict, tf_results: list, mtf: dict,
                        entry_points: list, price_info: dict,
                        api_key: str) -> str:
    """
    Gemini APIを呼び出して分析コメントを生成する

    Returns: コメント文字列（失敗時は空文字）
    """
    if not api_key:
        return ""

    prompt = _build_prompt(symbol, tf_results, mtf, entry_points, price_info)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 800,
            "temperature": 0.7,
        }
    }

    url = f"{GEMINI_API_URL}?key={api_key}"
    data = json.dumps(payload).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # レスポンスからテキストを取得
        text = (result
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", ""))
        return text.strip()

    except urllib.error.HTTPError as e:
        print(f"  [WARNING] Gemini API HTTP Error {e.code}: {e.reason}")
        return ""
    except Exception as e:
        print(f"  [WARNING] Gemini API Error: {e}")
        return ""


def build_price_info(tf_results: list) -> dict:
    """
    直近高値・安値・現在値の位置情報を構築
    日足のスイングポイントを使用
    """
    info = {
        "current": None,
        "swing_high": None,
        "swing_low": None,
        "pct_from_high": None,
        "pct_from_low": None,
        "range_position": None,
    }

    # 日足を優先、なければ週足
    daily = None
    for label in ["Daily", "日足", "Weekly", "週足"]:
        match = next((r for tf, r in tf_results if tf["label"] == label), None)
        if match:
            daily = match
            break

    if not daily:
        return info

    st  = daily.get("st") or {}
    dow = daily.get("dow") or {}

    if not st or not dow:
        return info

    # 現在値
    current = st.get("close")
    info["current"] = current

    # 直近スイング高値・安値
    highs = dow.get("swing_highs", [])
    lows  = dow.get("swing_lows",  [])

    if highs:
        info["swing_high"] = highs[-1][1]
    if lows:
        info["swing_low"] = lows[-1][1]

    # 現在値の位置を計算
    if current and info["swing_high"] and info["swing_low"]:
        h = info["swing_high"]
        l = info["swing_low"]

        if h != 0:
            info["pct_from_high"] = (current - h) / h * 100
        if l != 0:
            info["pct_from_low"] = (current - l) / l * 100

        # レンジ内の位置（0%=安値, 100%=高値）
        rng = h - l
        if rng > 0:
            info["range_position"] = (current - l) / rng * 100

    return info
