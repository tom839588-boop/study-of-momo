"""DeepSeek API 封装：余额查询，错误分类。"""

from dataclasses import dataclass

import httpx

BASE_URL = "https://api.deepseek.com"


class APIKeyInvalidError(Exception):
    """API Key 无效或被吊销。"""
    pass


class APIConnectionError(Exception):
    """网络连接失败。"""
    pass


@dataclass
class BalanceInfo:
    is_available: bool
    total_balance: float
    granted_balance: float
    topped_up_balance: float
    currency: str


def get_balance(api_key: str) -> BalanceInfo:
    """查询账户余额。"""
    try:
        resp = httpx.get(
            f"{BASE_URL}/user/balance",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=15,
        )
    except httpx.TimeoutException:
        raise APIConnectionError("请求超时")
    except httpx.NetworkError:
        raise APIConnectionError("网络连接失败")

    if resp.status_code == 401:
        raise APIKeyInvalidError("API Key 无效或被吊销，请检查 DeepSeek 账户")

    resp.raise_for_status()
    data = resp.json()

    info = data["balance_infos"][0]
    return BalanceInfo(
        is_available=data.get("is_available", True),
        total_balance=float(info["total_balance"]),
        granted_balance=float(info["granted_balance"]),
        topped_up_balance=float(info["topped_up_balance"]),
        currency=info["currency"],
    )


def check_api_key(api_key: str) -> bool:
    """验证 API Key 是否有效。"""
    try:
        get_balance(api_key)
        return True
    except Exception:
        return False
