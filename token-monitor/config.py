"""配置管理：环境变量、用户偏好持久化、告警阈值。"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

CONFIG_DIR = Path.home() / ".token-monitor"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_REFRESH_INTERVAL = 15  # 分钟
REFRESH_OPTIONS = [5, 15, 30]  # 可选刷新间隔
DEFAULT_DAILY_ALERT = 50.0     # 每日消费超过 50 元告警
DEFAULT_SINGLE_DROP_ALERT = 10.0  # 单次刷新余额下降超过 10 元告警
DEFAULT_ALERT_ENABLED = True   # 告警默认开启


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2))


def get_api_key() -> Optional[str]:
    """从环境变量读取 DeepSeek API Key。"""
    return os.environ.get("DEEPSEEK_API_KEY")


def get_refresh_interval() -> int:
    cfg = load_config()
    interval = cfg.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)
    if interval not in REFRESH_OPTIONS:
        interval = DEFAULT_REFRESH_INTERVAL
    return interval


def set_refresh_interval(minutes: int) -> None:
    cfg = load_config()
    cfg["refresh_interval"] = minutes
    save_config(cfg)


# ---- Alert settings ----


def get_alert_config() -> Dict[str, Any]:
    cfg = load_config()
    alerts = cfg.get("alerts", {})
    return {
        "enabled": alerts.get("enabled", DEFAULT_ALERT_ENABLED),
        "daily_threshold": alerts.get("daily_threshold", DEFAULT_DAILY_ALERT),
        "single_drop_threshold": alerts.get("single_drop_threshold", DEFAULT_SINGLE_DROP_ALERT),
    }


def set_alert_enabled(enabled: bool) -> None:
    cfg = load_config()
    alerts = cfg.setdefault("alerts", {})
    alerts["enabled"] = enabled
    save_config(cfg)


def set_daily_alert_threshold(value: float) -> None:
    cfg = load_config()
    alerts = cfg.setdefault("alerts", {})
    alerts["daily_threshold"] = value
    save_config(cfg)


def set_single_drop_alert_threshold(value: float) -> None:
    cfg = load_config()
    alerts = cfg.setdefault("alerts", {})
    alerts["single_drop_threshold"] = value
    save_config(cfg)


DAILY_THRESHOLD_OPTIONS = [10.0, 20.0, 50.0, 100.0, 200.0]
DROP_THRESHOLD_OPTIONS = [5.0, 10.0, 20.0, 50.0]
