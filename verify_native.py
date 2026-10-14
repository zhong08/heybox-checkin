"""Live verification of the submit endpoint; no notification is sent."""
import time
from heybox import check_in
from utils import setup_logging

if __name__ == "__main__":
    setup_logging()
    started = time.monotonic()
    outcome = check_in()
    print("提交接口：", outcome.status, outcome.message)
    assert outcome.status in ("签到成功", "今日已签到"), "Native submit signature was not accepted"
    assert outcome.details, "Current-day native state query was not accepted"
    print(outcome.details)
    print("真实原生签名验证通过；用时", round(time.monotonic() - started, 2), "秒；没有发送通知。")
