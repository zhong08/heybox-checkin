"""真实接口来源与签名许可证见 SOURCES.md、THIRD_PARTY_LICENSES.txt。"""
import hashlib
import secrets
import time
from dataclasses import dataclass
from itertools import zip_longest

import requests

from config import credentials, value
from native_sign import signed_params as native_params
from utils import log, redact, request_json

BASE_URL = "https://api.xiaoheihe.cn"
SIGN_PATH = "/task/sign_v3/sign"
TASK_PATH = "/task/list_v2/"
STATE_PATH = "/task/sign_v3/get_sign_state"
ALPHABET = "AB45STUVWZEFGJ6CH01D237IXYPQRKLMN89"
WEB_PARAMS = {"os_type": "web", "version": "999.0.4", "x_app": "heybox_website",
              "app": "web", "client_type": "web", "web_version": "2.5",
              "x_client_type": "web", "x_os_type": "Windows", "device_info": "Chrome"}
HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
           "Referer": "https://xiaoheihe.cn/", "Origin": "https://www.xiaoheihe.cn"}


def md5(text):
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def sign(path, timestamp, nonce):
    # Port of XiaHouSheng/heybox-core process_origin.js (MIT), checked against JS.
    path = "/" + "/".join(part for part in path.split("/") if part) + "/"
    def mapped(text, alphabet):
        return "".join(alphabet[ord(c) % len(alphabet)] for c in text)
    parts = (mapped(str(timestamp + 1), ALPHABET[:-2]), mapped(path, ALPHABET), mapped(nonce, ALPHABET))
    seed = "".join("".join(group) for group in zip_longest(*parts, fillvalue=""))[:20]
    digest = md5(seed)
    encoded = mapped(digest[:5], ALPHABET[:-4])
    def e(v):
        return ((v << 1) ^ (27 if v & 128 else 0)) & 255
    def z(v):
        return e(v) ^ v
    def j(v):
        return z(e(v))
    def aa(v):
        return j(z(e(v)))
    def o(v):
        return aa(v) ^ j(v) ^ z(v)
    a, b, c, d, x, y = map(ord, digest[-6:])
    checksum = sum((o(a) ^ aa(b) ^ j(c) ^ z(d), z(a) ^ o(b) ^ aa(c) ^ j(d),
                    j(a) ^ z(b) ^ o(c) ^ aa(d), aa(a) ^ j(b) ^ z(c) ^ o(d), x, y)) % 100
    return f"{encoded}{checksum:02d}"


def signed_params(path):
    timestamp = int(time.time())
    nonce = md5(f"{timestamp}{secrets.token_hex(16)}").upper()
    return {**WEB_PARAMS, "_time": timestamp,
            "nonce": nonce, "hkey": sign(path, timestamp, nonce)}


@dataclass(frozen=True)
class Result:
    status: str
    message: str
    details: str = ""


def parse_result(data):
    status = data.get("status")
    result = data.get("result")
    result = result if isinstance(result, dict) else {}
    message = redact(str(data.get("msg") or data.get("message") or result.get("error_msg") or ""))[:400]
    if status in ("login", "lack_token", "need_login", "unauthorized", "login_required", "relogin"):
        return Result("登录失效", "登录凭证失效，请更新 .env 中的小黑盒凭证")
    if status != "ok":
        return Result("API 返回异常", message or f"无法识别的 API 状态：{str(status)[:80]}")
    state = result.get("state", data.get("state"))
    if state == "success":
        return Result("签到成功", message or "服务器确认签到成功")
    if state == "ignore":
        return Result("今日已签到", message or "今天已经完成签到")
    if state in (None, ""):
        return Result("签到结果待确认", "签到接口未返回明确状态，尚未确认今日签到记录")
    return Result("API 返回异常", message or f"无法确认签到结果，state={str(state)[:80]}")


def sign_task(data):
    if data.get("status") != "ok" or not isinstance(data.get("result"), dict):
        return {}
    groups = data["result"].get("task_list", [])
    if not isinstance(groups, list):
        return {}
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("tasks"), list):
            continue
        for task in group["tasks"]:
            if not isinstance(task, dict) or task.get("type") != "sign":
                continue
            return task
    return {}


def task_details(data):
    task = sign_task(data)
    lines = []
    awards = task.get("award_desc_v2", [])
    if isinstance(awards, list):
        descriptions = [str(a["desc"])[:100] for a in awards if isinstance(a, dict) and a.get("desc")]
        if descriptions:
            lines.append("签到任务奖励（服务器原文）：" + "，".join(descriptions))
    if task.get("sign_in_streak") is not None:
        lines.append(f"连续签到：{str(task['sign_in_streak'])[:40]} 天")
    result = data.get("result")
    user = result.get("user") if isinstance(result, dict) else None
    level = user.get("level_info") if isinstance(user, dict) else None
    if isinstance(level, dict) and level.get("level") is not None:
        lines.append(f"当前等级：{str(level['level'])[:40]}")
    return redact("\n".join(lines))


def state_details(data):
    result = data.get("result")
    if data.get("status") != "ok" or not isinstance(result, dict) or result.get("state") != "ok":
        return ""
    lines = []
    if result.get("sign_in_exp") is not None:
        lines.append("服务器今日签到记录：经验 " + str(result["sign_in_exp"])[:40])
    if result.get("sign_in_coin") is not None:
        lines.append("服务器今日签到记录：H币 " + str(result["sign_in_coin"])[:40])
    if result.get("sign_in_streak") is not None:
        lines.append("连续签到：" + str(result["sign_in_streak"])[:40] + " 天")
    level = result.get("level_info")
    if isinstance(level, dict) and level.get("level") is not None:
        lines.append("当前等级：" + str(level["level"])[:40])
    return redact("\n".join(lines))


def check_in():
    account, cookie = credentials()
    log.info("开始执行小黑盒签到，账号：%s", account)
    with requests.Session() as session:
        session.headers.update({"Accept": "application/json", "User-Agent": "Max-Android", "Cookie": cookie})
        log.info("正在提交签到；服务器同时检查登录状态和是否重复签到")
        submitted = request_json(session, "GET", BASE_URL + SIGN_PATH,
                                 params=lambda: native_params(SIGN_PATH, account))
        body = submitted.get("result")
        body = body if isinstance(body, dict) else {}
        log.info("提交响应摘要：status=%s；state=%r；signed_date=%s", str(submitted.get("status"))[:80],
                 str(body.get("state", submitted.get("state")))[:80], str(body.get("signed_date"))[:40])
        outcome = parse_result(submitted)
        log.info("签到状态：%s；%s", outcome.status, outcome.message)
        if outcome.status in ("签到成功", "今日已签到", "签到结果待确认"):
            try:
                state = request_json(session, "GET", BASE_URL + STATE_PATH,
                                     params=lambda: native_params(STATE_PATH, account))
                record = state.get("result")
                record = record if isinstance(record, dict) else {}
                # signed_date counts calendar days since 1970 in the Beijing timezone.
                today = int((time.time() + 8 * 3600) // 86400)
                confirmed = state.get("status") == "ok" and record.get("state") == "ok" \
                    and type(record.get("signed_date")) is int and record["signed_date"] == today
                log.info("今日记录核验：status=%s；state=%r；signed_date=%s；北京时间日编号=%s；确认=%s",
                         str(state.get("status"))[:80], str(record.get("state"))[:80],
                         str(record.get("signed_date"))[:40], today, confirmed)
                if confirmed and outcome.status == "签到结果待确认":
                    outcome = Result("今日已签到", "提交响应未给出明确状态，已通过服务器今日记录确认签到完成")
                details = state_details(state) if confirmed else ""
                outcome = Result(outcome.status, outcome.message, details)
                if details:
                    log.info("%s", details)
                if not confirmed:
                    log.warning("未取得有效的今日签到记录，保留提交状态：%s", outcome.status)
            except Exception as exc:
                log.warning("今日记录查询失败，保留提交状态 %s：%s", outcome.status, type(exc).__name__)
                if outcome.status == "签到结果待确认":
                    outcome = Result(outcome.status, f"提交响应缺少明确状态，今日记录查询失败（{type(exc).__name__}）")
    return outcome
