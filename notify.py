import re

import requests

from config import notification_provider, value
from utils import log, redact, request_json


def send_serverchan(title, content):
    key = value("SERVERCHAN_SENDKEY")
    if key.startswith("sctp"):
        match = re.fullmatch(r"sctp(\d+)t[A-Za-z0-9]+", key)
        if not match:
            raise ValueError("Server酱³ SendKey 格式错误")
        url = f"https://{match[1]}.push.ft07.com/send/{key}.send"
    else:
        if not re.fullmatch(r"SCT[A-Za-z0-9]+", key):
            raise ValueError("Server酱 Turbo SendKey 应以 SCT 开头")
        url = f"https://sctapi.ftqq.com/{key}.send"
    with requests.Session() as session:
        data = request_json(session, "POST", url, json={"title": title, "desp": content})
    if data.get("code") != 0:
        raise ValueError("Server酱 API 拒绝通知：" + redact(data.get("message", data.get("msg", "未提供原因")))[:300])


def send_pushplus(title, content):
    with requests.Session() as session:
        data = request_json(session, "POST", "https://www.pushplus.plus/send", json={
            "token": value("PUSHPLUS_TOKEN"), "title": title, "content": content,
            "template": "markdown", "channel": "wechat"})
    if data.get("code") != 200:
        raise ValueError("PushPlus API 拒绝通知：" + redact(data.get("msg", "未提供原因"))[:300])


def send_wxpusher(title, content):
    token, uid = value("WXPUSHER_APP_TOKEN"), value("WXPUSHER_UID")
    if not re.fullmatch(r"AT_[A-Za-z0-9]+", token) or not re.fullmatch(r"UID_[A-Za-z0-9]+", uid):
        raise ValueError("WxPusher 应用令牌应以 AT_ 开头，接收用户应以 UID_ 开头")
    with requests.Session() as session:
        data = request_json(session, "POST", "https://wxpusher.zjiecode.com/api/send/message", json={
            "appToken": token, "uids": [uid], "summary": title[:100],
            "content": title + "\n\n" + content, "contentType": 1})
    if data.get("code") != 1000:
        raise ValueError("WxPusher API 拒绝通知：" + redact(str(data.get("msg", "未提供原因")))[:300])
    records = data.get("data")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise ValueError("WxPusher 未返回接收用户的受理结果")
    if records[0].get("uid") != uid:
        raise ValueError("WxPusher 返回的接收用户不匹配")
    if records[0].get("code") != 1000:
        raise ValueError("WxPusher 接收用户未受理：" + redact(str(records[0].get("status", "未提供原因")))[:300])


def send_notification(title, content):
    try:
        provider = notification_provider()
        log.info("正在发送通知：%s", provider)
        sender = {"serverchan": send_serverchan, "pushplus": send_pushplus, "wxpusher": send_wxpusher}[provider]
        sender(redact(title).replace("\n", " "), redact(content))
        log.info("通知状态：成功（推送服务已受理，请在接收端确认收件）")
        return True
    except requests.RequestException as exc:
        log.error("通知状态：失败，网络/HTTP 异常 %s%s", type(exc).__name__,
                  f" HTTP {exc.response.status_code}" if exc.response is not None else "")
    except Exception as exc:
        log.error("通知状态：失败，%s", redact(str(exc)) if isinstance(exc, ValueError) else type(exc).__name__)
    return False
