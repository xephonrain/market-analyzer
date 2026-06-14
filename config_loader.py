#!/usr/bin/env python3
# ============================================================
#  config_loader.py
#  config.json があればそちらを優先、なければ config.py を使用
# ============================================================
import json, os

_BASE = os.path.dirname(__file__)

def load_config() -> dict:
    json_path = os.path.join(_BASE, "config.json")
    if os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as f:
            cfg = json.load(f)
        print(f"  [config] config.json を使用")
        return cfg
    # fallback: config.py
    print(f"  [config] config.py を使用（config.json が見つかりません）")
    from config import SYMBOLS, TIMEFRAMES, SUPERTREND_PARAMS, DOW_PARAMS, PICKUP_CONDITIONS
    return {
        "symbols":           SYMBOLS,
        "timeframes":        TIMEFRAMES,
        "pickup_conditions": PICKUP_CONDITIONS,
        "supertrend_params": SUPERTREND_PARAMS,
        "dow_params":        DOW_PARAMS,
    }
