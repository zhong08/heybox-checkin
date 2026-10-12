"""扫码获取真实凭据，不输出 Cookie；不执行签到或发送通知。"""
import argparse
import json
import os
import time
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import set_key

from config import ROOT
from heybox import BASE_URL, HEADERS, signed_params
from utils import request_json, setup_logging

STATE = ROOT / "login-state.json"


def create():
    path = "/account/get_qrcode_url/"
    with requests.Session() as session:
        session.headers.update(HEADERS)
        data = request_json(session, "GET", BASE_URL + path, params={**signed_params(path), "app": "web"})
        if data.get("status") != "ok" or not isinstance(data.get("result"), dict):
            raise ValueError("小黑盒拒绝创建二维码，未获取到登录凭据")
        url = data["result"].get("qr_url", "")
        token = parse_qs(urlparse(url).query).get("qr", [""])[0]
        if not token or not url.startswith("https://"):
            raise ValueError("二维码接口返回格式已变化")
        STATE.touch(mode=0o600, exist_ok=True)
        STATE.write_text(json.dumps({"qr": token, "cookies": session.cookies.get_dict()}), encoding="utf-8")
        os.chmod(STATE, 0o600)
        print("二维码登录地址（临时有效）：" + url)


def poll():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    path = "/account/qr_state/"
    with requests.Session() as session:
        session.headers.update(HEADERS)
        session.cookies.update(state.get("cookies", {}))
        data = request_json(session, "GET", BASE_URL + path, params={**signed_params(path), "app": "web", "qr": state["qr"]})
        if data.get("status") != "ok" or not isinstance(data.get("result"), dict):
            raise ValueError("扫码登录请求被拒绝，可能需要在官方客户端完成验证")
        result = data["result"]
        status = result.get("error")
        if status in ("wait", "ready"):
            print("等待扫码" if status == "wait" else "已扫码，请在手机确认登录")
            return False
        if status != "ok":
            raise ValueError("二维码已失效，请重新创建")
        cookies = session.cookies.get_dict()
        profile = result.get("profile") or {}
        detail = result.get("account_detail") or {}
        account = str(profile.get("heybox_id") or detail.get("userid") or result.get("heybox_id") or cookies.get("heybox_id") or cookies.get("x_xhh_heyboxid") or "")
        pkey = str(result.get("pkey") or cookies.get("pkey") or cookies.get("user_pkey") or "")
        if not account or not pkey:
            raise ValueError("登录成功响应缺少账号或 pkey，未保存")
        cookies.update({"heybox_id": account, "user_heybox_id": account, "pkey": pkey, "user_pkey": pkey,
                        "x_xhh_heyboxid": str(result.get("x_xhh_heyboxid") or account)})
        env = ROOT / ".env"
        env.touch(mode=0o600, exist_ok=True)
        os.chmod(env, 0o600)
        for key, val in {"HEYBOX_ID": account, "HEYBOX_PKEY": pkey,
                         "HEYBOX_TOKEN": cookies.get("x_xhh_tokenid", ""),
                         "HEYBOX_COOKIE": "; ".join(f"{k}={v}" for k, v in cookies.items())}.items():
            set_key(str(env), key, val)
        os.chmod(env, 0o600)
        STATE.unlink(missing_ok=True)
        print("登录成功，凭据已写入 .env（未显示任何密钥）；是否可签到仍需真实测试。")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小黑盒扫码登录辅助工具")
    parser.add_argument("action", choices=("create", "poll", "watch"))
    args = parser.parse_args()
    setup_logging()
    try:
        if args.action == "create":
            create()
        elif args.action == "poll":
            poll()
        else:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if poll():
                    break
                time.sleep(3)
            else:
                raise ValueError("等待扫码超时，请重新创建二维码")
    except Exception as exc:
        print(str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else type(exc).__name__)
        raise SystemExit(1)
