"""Validated Android 1.3.385 native signer; Java runs only during each request."""
import json
import os
import re
import subprocess

from config import ROOT, value


class NativeSignError(RuntimeError):
    """Controlled diagnostic; never includes child output or device metadata."""


def signed_params(path, account):
    model = value("HEYBOX_DEVICE_INFO")
    imei = value("HEYBOX_IMEI")
    debug_info = value("HEYBOX_DEBUG_INFO")
    if not model or not imei or not debug_info:
        raise ValueError("缺少安卓签名配置，请补齐 HEYBOX_DEVICE_INFO、HEYBOX_IMEI、HEYBOX_DEBUG_INFO")
    config = {"path": "/" + path.strip("/") + "/", "account": account, "model": model,
              "os_version": "16", "version": "1.3.385", "debug_info": debug_info}
    root = ROOT / "signer"
    command = [value("HEYBOX_JAVA", "java"), "-Xms16m", "-Xmx96m", "-Dorg.slf4j.simpleLogger.defaultLogLevel=error",
               "-cp", str(root / "native-signer.jar") + os.pathsep + str(root / "lib" / "*"), "NativeSigner", str(root)]
    try:
        # Only device metadata enters Java. Login and notification keys stay in Python.
        env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "LANG", "HOME") if key in os.environ}
        result = subprocess.run(command, input=json.dumps(config), capture_output=True, text=True, encoding="utf8",
                                timeout=45, check=True, env=env)
    except subprocess.TimeoutExpired:
        raise NativeSignError("原生签名超过 45 秒未完成") from None
    except subprocess.CalledProcessError as exc:
        raise NativeSignError(f"Java 签名进程异常退出（退出码 {exc.returncode}）") from None
    except OSError as exc:
        raise NativeSignError(f"无法启动 Java 签名进程（系统错误 {exc.errno}），请检查 Java 和 signer 文件") from None
    except UnicodeError:
        raise NativeSignError("原生签名模块返回格式异常：不是有效 UTF-8 文本") from None
    try:
        signed = json.loads(result.stdout)
        if set(signed) != {"_time", "nonce", "hkey", "_rnd"} or not re.fullmatch(r"[A-Za-z0-9]{32}", signed["nonce"]) \
                or not re.fullmatch(r"[0-9A-F]{1,8}", signed["hkey"]) or not re.fullmatch(r"14:[0-9A-F]{1,8}", signed["_rnd"]):
            raise ValueError
        int(signed["_time"])
    except (ValueError, TypeError, KeyError):
        raise NativeSignError("原生签名模块返回格式异常") from None
    return {"heybox_id": account, "imei": imei, "device_info": model, "os_type": "Android", "x_os_type": "Android",
            "x_client_type": "mobile", "os_version": "16", "version": "1.3.385", "build": "1092",
            "dw": "366", "channel": "heybox_oppo", "x_app": "heybox", "time_zone": "Asia/Shanghai", **signed}
