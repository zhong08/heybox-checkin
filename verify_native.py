"""Live verification of the submit endpoint; no notification is sent."""
import time
import requests
from config import credentials
from heybox import BASE_URL, STATE_PATH, SIGN_PATH, parse_result, state_details
from native_sign import signed_params
from utils import request_json

if __name__ == "__main__":
    account, cookie = credentials()
    started = time.monotonic()
    with requests.Session() as session:
        session.headers.update({"Cookie": cookie, "User-Agent": "Max-Android"})
        outcome = parse_result(request_json(session, "GET", BASE_URL + SIGN_PATH, params=lambda: signed_params(SIGN_PATH, account)))
        print("提交接口：", outcome.status, outcome.message)
        assert outcome.status in ("签到成功", "今日已签到"), "Native submit signature was not accepted"
        state = request_json(session, "GET", BASE_URL + STATE_PATH, params=lambda: signed_params(STATE_PATH, account))
        details = state_details(state)
        assert details, "Native state query was not accepted"
        print(details)
    print("真实原生签名验证通过；用时", round(time.monotonic() - started, 2), "秒；没有发送通知。")
