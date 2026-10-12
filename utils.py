import logging
import re
import sys
import time
from http.cookies import SimpleCookie
from logging.handlers import RotatingFileHandler
from urllib.parse import quote, quote_plus

import requests

from config import ROOT, value

log = logging.getLogger("heybox")


def mask(secret):
    return secret[:4] + "****" + secret[-4:] if len(secret) > 8 else "****"


def redact(text):
    secrets = [value(k) for k in ("HEYBOX_PKEY", "HEYBOX_TOKEN", "HEYBOX_COOKIE",
                                "SERVERCHAN_SENDKEY", "PUSHPLUS_TOKEN")]
    cookie = SimpleCookie()
    try:
        cookie.load(value("HEYBOX_COOKIE"))
        secrets.extend(v.value for k, v in cookie.items() if k.lower() in
                       ("pkey", "user_pkey", "x_xhh_tokenid", "token", "access_token"))
    except Exception:
        pass
    text = str(text)
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            for encoded in {secret, quote(secret, safe=""), quote_plus(secret)}:
                text = text.replace(encoded, mask(secret))
    return re.sub(r"(?i)((?:pkey|token|x_xhh_tokenid|sendkey|cookie)\s*[=:]\s*)[^\s;,]+",
                  r"\1****", text)


class SafeFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def setup_logging():
    (ROOT / "logs").mkdir(exist_ok=True)
    log.setLevel(logging.INFO)
    log.propagate = False
    if not log.handlers:
        for handler in (logging.StreamHandler(sys.stdout),
                        RotatingFileHandler(ROOT / "logs/heybox.log", maxBytes=1024 * 1024,
                                            backupCount=3, encoding="utf-8")):
            handler.setFormatter(SafeFormatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
            log.addHandler(handler)


def request_json(session, method, url, **kwargs):
    """最多三次尝试，退避 1/2 秒；不记录可能包含密钥的 URL。"""
    for attempt in range(3):
        try:
            options = dict(kwargs)
            if callable(options.get("params")):
                options["params"] = options["params"]()
            response = session.request(method, url, timeout=10, allow_redirects=False, **options)
            log.info("%s HTTP %s", method, response.status_code)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                response.close()
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            if not 200 <= response.status_code < 300:
                raise ValueError("HTTP 返回重定向，拒绝转发凭证")
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("API JSON 顶层不是对象")
            return data
        except requests.exceptions.JSONDecodeError:
            raise ValueError("JSON 解析异常：服务器没有返回有效 JSON") from None
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == 2:
                raise
            log.warning("网络请求异常 %s，%s 秒后重试", type(exc).__name__, 2 ** attempt)
            time.sleep(2 ** attempt)
