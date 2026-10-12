"""配置只从环境变量和项目目录的 .env 读取。"""
import os
from http.cookies import SimpleCookie
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def value(name, default=""):
    return os.getenv(name, default).strip()


def credentials():
    cookie = SimpleCookie()
    try:
        cookie.load(value("HEYBOX_COOKIE"))
    except Exception:
        raise ValueError("HEYBOX_COOKIE 格式错误，请检查 .env") from None
    for name, env in (("pkey", "HEYBOX_PKEY"), ("heybox_id", "HEYBOX_ID"),
                      ("x_xhh_tokenid", "HEYBOX_TOKEN")):
        if value(env):
            cookie[name] = value(env)
    pkey = cookie.get("pkey") or cookie.get("user_pkey")
    account = cookie.get("heybox_id") or cookie.get("user_heybox_id") or cookie.get("x_xhh_heyboxid")
    if not pkey:
        raise ValueError("缺少 HEYBOX_PKEY，请检查 .env（或在 HEYBOX_COOKIE 中填写 pkey）")
    if not account:
        raise ValueError("缺少 HEYBOX_ID，请检查 .env（或在 HEYBOX_COOKIE 中填写 heybox_id）")
    return account.value, "; ".join(f"{k}={v.coded_value}" for k, v in cookie.items())


def notification_provider():
    provider = value("NOTIFY_PROVIDER").lower()
    if not provider:
        provider = "serverchan" if value("SERVERCHAN_SENDKEY") or not value("PUSHPLUS_TOKEN") else "pushplus"
    if provider not in ("serverchan", "pushplus"):
        raise ValueError("NOTIFY_PROVIDER 必须为 serverchan 或 pushplus")
    key = "SERVERCHAN_SENDKEY" if provider == "serverchan" else "PUSHPLUS_TOKEN"
    if not value(key):
        raise ValueError(f"缺少 {key}，请检查 .env")
    return provider
