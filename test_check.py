"""离线自检；不访问小黑盒、不发送微信通知。运行：python3.12 test_check.py"""
import json
import os
import subprocess
import sys
from unittest.mock import Mock, patch

import requests

import config
import main
import notify
import native_sign
from heybox import Result, check_in, parse_result, sign, task_details, state_details
from utils import redact, request_json


def response(status, body):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    result._content_consumed = True
    return result


def check():
    assert sign("/bbs/app/api/general/search/v1", 1700000000, "0123456789ABCDEF0123456789ABCDEF") == "YT27P47"
    assert sign("bbs/app/api/general/search/v1/", 1784911948, "ABCDEF0123456789ABCDEF0123456789") == "Y1X0S26"
    assert sign("/task/sign_v3/sign", 1700000000, "0123456789ABCDEF0123456789ABCDEF") == "ZPUVS54"
    assert parse_result({"status": "ok", "result": {"state": "success"}}).status == "签到成功"
    assert parse_result({"status": "ok", "state": "ignore"}).status == "今日已签到"
    assert parse_result({"status": "ok"}).status == "签到结果待确认"
    assert parse_result({"status": "ok", "result": {"state": ""}}).status == "签到结果待确认"
    assert parse_result({"status": "need_login"}).status == "登录失效"
    assert parse_result({"status": "failed", "msg": "错误"}).message == "错误"
    assert not task_details({"status": "ok", "result": {"task_list": None}})
    info = task_details({"status": "ok", "result": {"task_list": [{"tasks": [
        {"type": "sign", "award_desc_v2": [{"desc": "+40"}], "sign_in_streak": 1}]}]}})
    assert "+40" in info and "1 天" in info and "经验" not in info
    finished = {"status": "ok", "result": {"state": "ok", "signed_date": 17167,
                "sign_in_streak": 28, "sign_in_exp": 60, "sign_in_coin": 66}}
    assert "H币 66" in state_details(finished) and "经验 60" in state_details(finished)
    with patch("heybox.time.time", return_value=1483200060), \
            patch("heybox.credentials", return_value=("42", "pkey=test")), \
            patch("heybox.request_json", side_effect=[{"status": "ok", "result": {"state": "ignore"}}, finished]) as request:
        outcome = check_in()
        assert outcome.status == "今日已签到" and "28 天" in outcome.details
        assert request.call_count == 2
    for rejected in ({"status": "failed", "msg": "非法请求"},
                     {"status": "ok", "result": {"state": "fail"}}, {"status": "need_login"}):
        with patch("heybox.credentials", return_value=("42", "pkey=test")), \
                patch("heybox.request_json", return_value=rejected) as request:
            assert check_in().status not in ("签到成功", "今日已签到")
            request.assert_called_once()  # A rejected submission must not be replaced by existing sign state.
    with patch("heybox.credentials", return_value=("42", "pkey=test")), \
            patch("heybox.request_json", side_effect=[{"status": "ok", "result": {"state": "success"}}, requests.Timeout()]):
        assert check_in().status == "签到成功", "detail failures must preserve submit success"

    # At Beijing 2017-01-01 00:01, UTC is still yesterday. Empty submit states
    # require an authoritative current-day record, never status=ok alone.
    for submitted in ({"status": "ok", "result": {"state": ""}}, {"status": "ok"}):
        with patch("heybox.time.time", return_value=1483200060), \
                patch("heybox.credentials", return_value=("42", "pkey=test")), \
                patch("heybox.request_json", side_effect=[submitted, finished]) as request:
            outcome = check_in()
            assert outcome.status == "今日已签到" and "28 天" in outcome.details
            assert request.call_count == 2 and "今日记录确认" in outcome.message
    for invalid in ({"status": "failed", "result": finished["result"]},
                    {"status": "ok", "result": {**finished["result"], "state": "fail"}},
                    *({"status": "ok", "result": {**finished["result"], "signed_date": day}}
                      for day in (17166, 17168, None, "17167", True))):
        with patch("heybox.time.time", return_value=1483200060), \
                patch("heybox.credentials", return_value=("42", "pkey=test")), \
                patch("heybox.request_json", side_effect=[{"status": "ok", "result": {"state": ""}}, invalid]):
            outcome = check_in()
            assert outcome.status == "签到结果待确认" and not outcome.details
    with patch("heybox.credentials", return_value=("42", "pkey=test")), \
            patch("heybox.request_json", side_effect=[{"status": "ok", "result": {"state": ""}}, requests.Timeout()]):
        assert check_in().status == "签到结果待确认"

    with patch.dict(os.environ, {}, clear=True):
        try:
            config.credentials()
            assert False, "missing credentials should fail"
        except ValueError as exc:
            assert "HEYBOX_PKEY" in str(exc)
        os.environ.update(HEYBOX_COOKIE="pkey=privatekey123456; heybox_id=42; x_xhh_tokenid=secret789token")
        assert config.credentials()[0] == "42"
        assert "privatekey123456" not in redact("pkey=privatekey123456")
        assert "secret789token" not in redact("secret789token")
        os.environ["PUSHPLUS_TOKEN"] = "test-not-real"
        assert config.notification_provider() == "pushplus"
        os.environ["SERVERCHAN_SENDKEY"] = "SCTtestnotreal"
        assert config.notification_provider() == "serverchan"
        with patch("notify.request_json", return_value={"code": 0}) as request:
            notify.send_serverchan("test", "content")
            assert request.call_args.args[2] == "https://sctapi.ftqq.com/SCTtestnotreal.send"
        os.environ["SERVERCHAN_SENDKEY"] = "sctp123tTestNotReal"
        with patch("notify.request_json", return_value={"code": 0}) as request:
            notify.send_serverchan("test", "content")
            assert request.call_args.args[2] == "https://123.push.ft07.com/send/sctp123tTestNotReal.send"
        with patch("notify.request_json", return_value={"code": 400, "msg": "rejected"}):
            assert not notify.send_notification("test", "content")

    session = Mock()
    session.request.side_effect = [requests.Timeout(), response(503, {}), response(200, {"status": "ok"})]
    with patch("utils.time.sleep") as sleep:
        assert request_json(session, "GET", "https://example.invalid") == {"status": "ok"}
        assert [call.args[0] for call in sleep.call_args_list] == [1, 2]
    assert session.request.call_count == 3
    session.request.side_effect = [requests.Timeout(), response(200, {"status": "ok"})]
    with patch("utils.time.sleep"):
        params = Mock(side_effect=[{"nonce": "first"}, {"nonce": "fresh"}])
        request_json(session, "GET", "https://example.invalid", params=params)
        assert params.call_count == 2 and session.request.call_args.kwargs["params"] == {"nonce": "fresh"}
    assert session.request.call_args.kwargs["timeout"] == 10
    assert session.request.call_args.kwargs["allow_redirects"] is False
    session.request.reset_mock()
    session.request.side_effect = requests.Timeout()
    with patch("utils.time.sleep"):
        try:
            request_json(session, "GET", "https://example.invalid")
            assert False
        except requests.Timeout:
            assert session.request.call_count == 3
    broken = response(200, {})
    broken._content = b"<html>not JSON</html>"
    session.request.side_effect = None
    session.request.return_value = broken
    try:
        request_json(session, "GET", "https://example.invalid")
        assert False
    except ValueError as exc:
        assert "JSON" in str(exc)

    with patch.object(sys, "argv", ["main.py", "--test-notify"]), patch("main.setup_logging"), \
            patch("main.check_in") as mocked_check_in, patch("main.send_notification", return_value=True) as notification:
        assert main.main() == 0
        mocked_check_in.assert_not_called()
        notification.assert_called_once()
    with patch.object(sys, "argv", ["main.py"]), patch("main.setup_logging"), \
            patch("main.check_in", return_value=Result("签到成功", "done")), \
            patch("main.send_notification", return_value=False) as notification:
        assert main.main() == 2
        assert "签到成功" in notification.call_args.args[0]
    with patch.object(sys, "argv", ["main.py"]), patch("main.setup_logging"), \
            patch("main.check_in", return_value=Result("签到结果待确认", "unconfirmed")), \
            patch("main.send_notification", return_value=True) as notification:
        assert main.main() == 1
        assert "待确认" in notification.call_args.args[0] and "失败" not in notification.call_args.args[0]
    for failure in (ValueError("缺少 HEYBOX_PKEY"), requests.Timeout(), RuntimeError("secret")):
        with patch.object(sys, "argv", ["main.py"]), patch("main.setup_logging"), \
                patch("main.check_in", side_effect=failure), patch("main.send_notification", return_value=True) as notification:
            assert main.main() == 1
            notification.assert_called_once()
            if isinstance(failure, RuntimeError):
                assert "RuntimeError" in notification.call_args.args[1] and "secret" not in notification.call_args.args[1]
    with patch.dict(os.environ, {"HEYBOX_DEVICE_INFO": "RMX6688", "HEYBOX_IMEI": "test-device", "HEYBOX_DEBUG_INFO": "test-context"}), \
            patch("native_sign.subprocess.run", return_value=Mock(stdout=json.dumps(
                {"_time": "1791780466", "nonce": "A" * 32, "hkey": "1234ABCD", "_rnd": "14:5678ABCD"}))) as run:
        signed = native_sign.signed_params("/task/sign_v3/sign", "42")
        assert signed["os_type"] == "Android" and signed["hkey"] == "1234ABCD"
        assert json.loads(run.call_args.kwargs["input"])["path"] == "/task/sign_v3/sign/"
        assert "SERVERCHAN_SENDKEY" not in run.call_args.kwargs["env"]
        # Native uint32 hex strings omit leading zeroes; never pad or alter them.
        for hkey, rnd in (("0", "14:0"), ("123ABCD", "14:567ABCD"), ("1234ABCD", "14:5678ABCD")):
            run.return_value.stdout = json.dumps({"_time": "1791780466", "nonce": "A" * 32, "hkey": hkey, "_rnd": rnd})
            signed = native_sign.signed_params("/task/sign_v3/sign", "42")
            assert signed["hkey"] == hkey and signed["_rnd"] == rnd
        invalid = ["{}", "not-json-private-metadata"]
        for field, values in (("hkey", ("", "123456789", "G1234567", None)),
                              ("_rnd", ("14:", "14:123456789", "15:12345678", "14:XYZ")),
                              ("nonce", ("A" * 31, "A" * 33, "+" * 32))):
            for value in values:
                invalid.append(json.dumps({"_time": "1791780466", "nonce": "A" * 32,
                                           "hkey": "1234ABCD", "_rnd": "14:5678ABCD", field: value}))
        for output in invalid:
            run.return_value.stdout = output
            try:
                native_sign.signed_params("/task/sign_v3/sign", "42")
                assert False, "invalid native output should fail"
            except native_sign.NativeSignError as exc:
                assert str(exc) == "原生签名模块返回格式异常"
        for failure, reason in (
                (subprocess.TimeoutExpired("private-command", 45, output="private-output", stderr="private-stderr"), "超过 45 秒"),
                (subprocess.CalledProcessError(-9, "private-command", output="private-output", stderr="private-stderr"), "退出码 -9"),
                (FileNotFoundError(2, "private-path"), "系统错误 2"),
                (UnicodeDecodeError("utf8", b"\xff", 0, 1, "private-output"), "不是有效 UTF-8")):
            run.side_effect = failure
            with patch.object(sys, "argv", ["main.py"]), patch("main.setup_logging"), \
                    patch("main.check_in", side_effect=lambda: native_sign.signed_params("/task/sign_v3/sign", "42")), \
                    patch("main.send_notification", return_value=True) as notification:
                assert main.main() == 1
                notification.assert_called_once()
                content = notification.call_args.args[1]
                assert "原生签名失败" in content and reason in content
                assert "private-" not in content, "child diagnostics must not leak metadata"
    print("全部离线自检通过：签名、状态解析、脱敏、通知隔离、重试上限、异常通知。")


if __name__ == "__main__":
    check()
