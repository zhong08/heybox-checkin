# 飞牛小黑盒自动签到

Python 3.12 + Docker + cron：每天北京时间 **00:01** 提交签到，查询服务器记录，并通过 Server酱或 PushPlus 发送微信通知。运行完成后退出，无常驻 Android 或手机在线依赖。

**这是公开源码版。** 仓库不包含登录凭据、个人部署记录、App 原生库、APK 元数据或签名初始化数据。克隆后需自行准备兼容的签名资源并构建 Java 模块，才能执行真实签到。私人部署已验证 v3 提交返回 `status=ok, state=ignore`；公开源码的离线自检不会调用真实账号。

当前原生签名适配 App **1.3.385/build 1092、Android 16、初始化版本 14**。服务端升级或凭据过期可能需要重新适配。Python 执行网络和通知；Java 17+ / Unidbg 0.9.9 临时执行签名库。默认容器限制 300 MB 内存、1 核 CPU。

## 部署

1. 按 [签名模块说明](signer/README.md) 准备私人资源并构建签名模块。
2. 把项目放到飞牛 `/vol1/docker/heybox-checkin`（修改路径时同时修改 run.sh 和 cron）。
3. 创建 `.env` 并填写本人小黑盒移动端凭据、设备信息、DebugInfo，以及一个通知渠道。

```sh
test -f .env || cp .env.example .env
chmod 600 .env
mkdir -p logs
sudo docker compose build
sudo docker compose run --rm -T heybox
```

`HEYBOX_PKEY`、`HEYBOX_ID`、`HEYBOX_TOKEN`、`HEYBOX_COOKIE` 来自真实移动端会话；`HEYBOX_IMEI`、`HEYBOX_DEVICE_INFO`、`HEYBOX_DEBUG_INFO` 来自同一设备。不要编造参数或把 `.env` 提交到 Git。二维码辅助工具 login.py 只用于网页会话，不能代替移动端签名配置。

设置每天北京时间 00:01：

```sh
sudo chmod 750 /vol1/docker/heybox-checkin/run.sh
sudo cp heybox-checkin.cron /etc/cron.d/heybox-checkin
sudo chown root:root /etc/cron.d/heybox-checkin
sudo chmod 644 /etc/cron.d/heybox-checkin
sudo systemctl is-active cron
```

宿主机时区需为 Asia/Shanghai。flock 防止重叠运行。详细操作见 [飞牛部署教程](飞牛fnOS部署教程.md)。

## 通知和日志

填 `SERVERCHAN_SENDKEY` 或 `PUSHPLUS_TOKEN`；`NOTIFY_PROVIDER` 可指定 serverchan / pushplus。成功、今日已签到、登录失效和异常都会尝试通知。推送服务受理不等于微信终端已送达。

```sh
sudo docker compose run --rm -T heybox python main.py --test-notify
sudo tail -n 40 logs/last-run.log
```

退出码：0 表示签到成功/已签到且通知受理；1 表示签到或配置/API 异常；2 表示已确认签到成功/已签到，但通知失败。详情查询失败不会改写已确认的签到结果。业务日志轮转；每次网络请求最多三次尝试，重试重新计算签名。

## 验证

离线自检无需登录、Java 或私人资源：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python test_check.py
```

真实签名验证需先准备私人资源和 `.env`。会提交签到，不发送微信：

```sh
sudo docker compose run --rm -T -v "$PWD/verify_native.py:/app/verify_native.py:ro" heybox python verify_native.py
```

接口和代码来源见 [SOURCES.md](SOURCES.md)，第三方许可证见 [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) 和 signer/licenses/。私人资源仅保存在自己的部署目录。
