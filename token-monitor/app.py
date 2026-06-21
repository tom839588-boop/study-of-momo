"""DeepSeek Token Monitor — macOS 菜单栏应用，带异常用量告警。"""

import subprocess
from datetime import datetime
from typing import Optional, Set

import rumps

from config import (
    get_api_key,
    get_refresh_interval,
    set_refresh_interval,
    REFRESH_OPTIONS,
    get_alert_config,
    set_alert_enabled,
    set_daily_alert_threshold,
    set_single_drop_alert_threshold,
    DAILY_THRESHOLD_OPTIONS,
    DROP_THRESHOLD_OPTIONS,
)
from deepseek_api import get_balance, APIKeyInvalidError, APIConnectionError
from storage import (
    init_db,
    record_snapshot,
    get_last_drop,
    get_today_usage,
    get_month_usage,
    get_history,
    clear_history,
)


class TokenMonitorApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="DeepSeekMonitor",
            title="🔄 加载中...",
            quit_button="退出",
        )
        self.api_key = get_api_key()
        self.last_refresh_time: Optional[datetime] = None
        self.current_balance: Optional[float] = None
        self.current_currency: str = "CNY"

        # 防重复告警：已通知过的消息签名
        self._alerted_signatures: Set[str] = set()

        # ---- 菜单项 ----
        self.balance_item = rumps.MenuItem("💰 余额：--")
        self.today_usage_item = rumps.MenuItem("📊 今日消费：--")
        self.month_usage_item = rumps.MenuItem("📈 本月消费：--")
        self.last_refresh_item = rumps.MenuItem("上次刷新：--")
        self.refresh_now_item = rumps.MenuItem("🔄 立即刷新")
        self.clear_menu_item = rumps.MenuItem("🗑 清除历史数据")

        # 刷新间隔
        self.settings_menu = rumps.MenuItem("⚙️ 刷新间隔")
        self.interval_items = {}
        for mins in REFRESH_OPTIONS:
            item = rumps.MenuItem(f"{mins} 分钟")
            self.interval_items[mins] = item
            self.settings_menu.add(item)
        self.pause_item = rumps.MenuItem("暂停自动刷新")

        # ---- 告警菜单 ----
        self.alert_menu = rumps.MenuItem("🔔 告警设置")
        self.alert_toggle_item = rumps.MenuItem("启用告警 ✓")
        self.daily_threshold_menu = rumps.MenuItem("每日消费告警阈值")
        self.drop_threshold_menu = rumps.MenuItem("单次大额消费告警阈值")
        self.daily_threshold_items = {}
        self.drop_threshold_items = {}
        self._build_alert_submenus()

        self.alert_menu.add(self.alert_toggle_item)
        self.alert_menu.add(self.daily_threshold_menu)
        self.alert_menu.add(self.drop_threshold_menu)

        self.menu = [
            self.balance_item,
            None,
            self.today_usage_item,
            self.month_usage_item,
            None,
            self.refresh_now_item,
            self.settings_menu,
            self.pause_item,
            self.alert_menu,
            None,
            self.clear_menu_item,
            None,
            self.last_refresh_item,
        ]

        # ---- 初始化 ----
        init_db()

        if not self.api_key:
            self.title = "⚠️ 无 Key"
            self.balance_item.title = "❌ 请设置 DEEPSEEK_API_KEY 环境变量"
        else:
            self._start_timer()
            self._fetch_data()

    def _build_alert_submenus(self):
        """构建告警阈值子菜单。"""
        cfg = get_alert_config()
        curr_daily = cfg["daily_threshold"]
        curr_drop = cfg["single_drop_threshold"]

        for val in DAILY_THRESHOLD_OPTIONS:
            label = f"{val:g} 元"
            item = rumps.MenuItem(label)
            self.daily_threshold_items[val] = item
            self.daily_threshold_menu.add(item)

        for val in DROP_THRESHOLD_OPTIONS:
            label = f"{val:g} 元"
            item = rumps.MenuItem(label)
            self.drop_threshold_items[val] = item
            self.drop_threshold_menu.add(item)

    # ---- Timer ----

    def _start_timer(self, interval_minutes: Optional[int] = None):
        if hasattr(self, "_timer") and self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
        if interval_minutes is None:
            interval_minutes = get_refresh_interval()
        self._timer = rumps.Timer(self._on_timer, interval_minutes * 60)
        self._timer.start()

    def _stop_timer(self):
        if hasattr(self, "_timer") and self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def _on_timer(self, _):
        self._fetch_data()

    # ---- Data fetching ----

    def _fetch_data(self):
        if not self.api_key:
            return

        try:
            balance = get_balance(self.api_key)
            self.current_balance = balance.total_balance
            self.current_currency = balance.currency
            self.last_refresh_time = datetime.now()

            # 记录到本地，获取本次下降金额
            drop = record_snapshot(balance.total_balance, balance.currency)

            self._check_alerts(balance, drop)
            self._update_menu()

        except APIKeyInvalidError as e:
            self.title = "⚠️ Key 失效"
            self.balance_item.title = f"❌ {e}"
            self._alert("🔑 Key 失效", str(e))

        except APIConnectionError as e:
            self.balance_item.title = f"⚠️ {e}"
            if self.current_balance is not None:
                cs = "¥" if self.current_currency == "CNY" else "$"
                self.title = f"💎 {cs}{self.current_balance:,.2f}"

        except Exception as e:
            error_msg = str(e)[:80]
            self.title = "❌ 错误"
            self.balance_item.title = f"❌ {error_msg}"

    # ---- Alert system ----

    def _check_alerts(self, balance, drop: float):
        """检查是否需要触发告警。"""
        cfg = get_alert_config()
        if not cfg["enabled"]:
            return

        # 1) Key 不健康
        if not balance.is_available:
            self._alert(
                "⚠️ 余额不足",
                f"DeepSeek 账户余额不足，API 调用即将受限。当前余额：¥{balance.total_balance:.2f}",
            )

        # 2) 单次大额消费
        if drop >= cfg["single_drop_threshold"]:
            self._alert(
                "⚠️ 大额消费",
                f"单次刷新发现余额下降 ¥{drop:.2f}，超过阈值 ¥{cfg['single_drop_threshold']:g}",
            )

        # 3) 每日消费超限
        today = get_today_usage()
        if today["estimated_cost"] >= cfg["daily_threshold"]:
            self._alert(
                "⚠️ 日消费超限",
                f"今日累计消费 ¥{today['estimated_cost']:.2f}，超过阈值 ¥{cfg['daily_threshold']:g}",
            )

    def _alert(self, title: str, message: str):
        """发送 macOS 通知，相同内容不会重复弹。"""
        sig = f"{title}|{message}"
        if sig in self._alerted_signatures:
            return
        self._alerted_signatures.add(sig)
        rumps.notification(title, "", message)

        # 同时也写到菜单栏提示
        self.balance_item.title = f"🔔 {message[:40]}"

    def _update_menu(self):
        if self.current_balance is None:
            return

        currency_symbol = "¥" if self.current_currency == "CNY" else "$"
        balance_str = f"{self.current_balance:,.2f}"
        self.title = f"💎 {currency_symbol}{balance_str}"
        self.balance_item.title = f"💰 余额：{currency_symbol}{balance_str}"

        today = get_today_usage()
        month = get_month_usage()

        self.today_usage_item.title = (
            f"📊 今日消费：{currency_symbol}{today['estimated_cost']:,.4f}"
        )
        self.month_usage_item.title = (
            f"📈 本月消费：{currency_symbol}{month['estimated_cost']:,.2f}"
        )

        if self.last_refresh_time:
            time_str = self.last_refresh_time.strftime("%H:%M:%S")
            self.last_refresh_item.title = f"上次刷新：{time_str}"

        # 暂停/恢复按钮状态
        self.pause_item.title = "⏸️ 暂停自动刷新" if self._timer is not None else "▶️ 恢复自动刷新"

    # ---- Menu callbacks ----

    @rumps.clicked("🔄 立即刷新")
    def on_refresh(self, _):
        self._fetch_data()

    @rumps.clicked("⏸️ 暂停自动刷新")
    def on_toggle_pause(self, _):
        if self._timer is None:
            self._start_timer()
        else:
            self._stop_timer()
        self._update_menu()

    @rumps.clicked("▶️ 恢复自动刷新")
    def on_resume(self, _):
        self._start_timer()
        self._update_menu()

    @rumps.clicked("💰 余额：--")
    def on_balance_click(self, _):
        if self.current_balance is not None:
            currency_symbol = "¥" if self.current_currency == "CNY" else "$"
            balance_str = f"{self.current_balance:,.2f}"
            text = f"{currency_symbol}{balance_str}"
            subprocess.run(["pbcopy"], input=text.encode(), check=False)
            rumps.notification("余额已复制", "", f"余额 {text} 已复制到剪贴板")

    @rumps.clicked("🗑 清除历史数据")
    def on_clear(self, _):
        clear_history()
        self._alerted_signatures.clear()
        self._update_menu()
        rumps.notification("已清除", "", "历史数据已清除")

    # ---- Alert toggles ----

    @rumps.clicked("启用告警 ✓")
    def on_toggle_alert(self, _):
        cfg = get_alert_config()
        set_alert_enabled(not cfg["enabled"])
        self.alert_toggle_item.title = "启用告警 ✓" if not cfg["enabled"] else "启用告警 ✗"
        rumps.notification("告警设置", "", f"告警已{'开启' if not cfg['enabled'] else '关闭'}")

    @rumps.clicked("启用告警 ✗")
    def on_enable_alert(self, _):
        set_alert_enabled(True)
        self.alert_toggle_item.title = "启用告警 ✓"
        rumps.notification("告警设置", "", "告警已开启")

    # ---- Daily threshold settings ----

    @rumps.clicked("10 元")
    @rumps.clicked("0.5 元")
    @rumps.clicked("1 元")
    @rumps.clicked("5 元")
    @rumps.clicked("10 元")
    @rumps.clicked("20 元")
    @rumps.clicked("50 元")
    def on_daily_threshold(self, sender):
        value = float(sender.title.replace("元", "").strip())
        set_daily_alert_threshold(value)
        self.daily_threshold_menu.title = f"每日消费告警阈值（{value:g}元）"
        rumps.notification("告警阈值", "", f"每日消费阈值设为 ¥{value:g}")

    # ---- Drop threshold settings ----

    @rumps.clicked("0.5 元")
    @rumps.clicked("1 元")
    @rumps.clicked("5 元")
    @rumps.clicked("10 元")
    @rumps.clicked("20 元")
    @rumps.clicked("50 元")
    def on_drop_threshold(self, sender):
        value = float(sender.title.replace("元", "").strip())
        set_single_drop_alert_threshold(value)
        self.drop_threshold_menu.title = f"单次大额消费告警阈值（{value:g}元）"
        rumps.notification("告警阈值", "", f"单次消费阈值设为 ¥{value:.0f}")

    # ---- Refresh interval settings ----

    @rumps.clicked("5 分钟")
    def on_set_5(self, _):
        set_refresh_interval(5)
        self._start_timer(5)
        self._update_menu()

    @rumps.clicked("15 分钟")
    def on_set_15(self, _):
        set_refresh_interval(15)
        self._start_timer(15)
        self._update_menu()

    @rumps.clicked("30 分钟")
    def on_set_30(self, _):
        set_refresh_interval(30)
        self._start_timer(30)
        self._update_menu()


if __name__ == "__main__":
    TokenMonitorApp().run()
