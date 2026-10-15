import argparse
import time
from datetime import datetime, timedelta, timezone

import requests

from config import value
from heybox import Result, check_in
from native_sign import NativeSignError
from notify import send_notification
from utils import log, redact, setup_logging


def main():
    parser = argparse.ArgumentParser(description="飞牛小黑盒自动签到")
    parser.add_argument("--test-notify", action="store_true", help="只测试通知")
    args = parser.parse_args()
    setup_logging()
    start = time.monotonic()
    if args.test_notify:
        ok = send_notification("飞牛小黑盒签到测试", "通知配置成功。\n\n如果收到这条消息，说明飞牛 NAS 通知已经配置正确。")
        return 0 if ok else 2
    try:
        result = check_in()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "未知"
        result = Result("登录失效" if status == 401 else "HTTP 状态异常", f"HTTP {status}")
    except requests.RequestException as exc:
        result = Result("网络请求失败", type(exc).__name__)
    except NativeSignError as exc:
        result = Result("原生签名失败", str(exc))
    except ValueError as exc:
        message = redact(str(exc))
        result = Result("JSON 解析异常" if "JSON" in message else "配置/API 异常", message)
    except Exception as exc:
        result = Result("未知异常", type(exc).__name__)
    log.info("最终签到状态：%s；%s", result.status, result.message)
    if result.details:
        log.info("%s", result.details)
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    content = f"账号：{value('HEYBOX_ID') or '见 Cookie 配置'}\n\n状态：{result.status}\n\n{result.message}\n\n{result.details}\n\n签到时间：{now}\n\n运行设备：飞牛 fnOS"
    title = {"签到成功": "小黑盒签到成功 ✅", "今日已签到": "小黑盒今日已签到 ☑️",
             "签到结果待确认": "⚠️ 小黑盒签到结果待确认",
             "登录失效": "⚠️ 小黑盒登录失效"}.get(result.status, "❌ 小黑盒签到失败")
    notified = send_notification(title, content)
    log.info("本次任务完成，耗时 %.2f 秒；签到=%s；通知=%s", time.monotonic() - start,
             result.status, "成功" if notified else "失败")
    if result.status not in ("签到成功", "今日已签到"):
        return 1
    return 0 if notified else 2


if __name__ == "__main__":
    raise SystemExit(main())
