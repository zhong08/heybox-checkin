# 飞牛 fnOS 部署教程

这份教程针对 YOUR_NAS_IP 上的 `/vol1/docker/heybox-checkin`，Python 固定 3.12，容器内附带 Java 和原生签名模块。每天执行时间按用户最新要求为北京时间 00:01。日常任务不需要手机或电脑在线。

## 1. 进入飞牛 SSH

在哪里：这台 Windows 电脑的 PowerShell。

输入：

```powershell
ssh admin@YOUR_NAS_IP
```

看到什么：首次连接确认主机指纹；之后输入自己的飞牛密码，输入时不显示字符。成功后提示符类似 `admin@nas:~$`。

下一步：检查时区和 Docker。

## 2. 检查环境

在哪里：SSH 窗口。

输入：

```sh
date
timedatectl
sudo docker compose version
```

看到什么：北京时间、Asia/Shanghai、Docker Compose v2.x。sudo 若要求密码，输入自己的飞牛密码。

下一步：进入项目目录。不要修改系统自带的 Python 3.11。

## 3. 放置项目

在哪里：飞牛文件管理或 SSH。

输入（按实际存储路径调整目录）：

```sh
sudo mkdir -p /vol1/docker/heybox-checkin/logs
cd /vol1/docker/heybox-checkin
pwd
ls -a
```

看到什么：pwd 显示 `/vol1/docker/heybox-checkin`；ls 应包含 main.py、Dockerfile、docker-compose.yml 等项目文件。

下一步：确认 .env。新设备需先上传整个项目目录；公开版需先按 signer/README.md 补齐签名资源并构建 Java 模块。

## 4. 填写凭据

在哪里：飞牛项目目录。

输入（只在 .env 不存在时复制，避免覆盖已经保存的密钥）：

```sh
test -f .env || cp .env.example .env
chmod 600 .env
nano .env
```

看到什么：配置编辑页面。若没有 nano，可在飞牛文件管理的文本编辑功能打开 .env；不要把完整内容粘贴到公开论坛。

下一步：填写真实小黑盒凭据和 Server酱 SendKey。nano 中 Ctrl+O 保存、回车确认、Ctrl+X 退出。填写自己的凭据，不要提交 .env。

## 5. 构建 Python 3.12 镜像

在哪里：SSH，项目目录。

输入：

```sh
sudo docker compose build
sudo docker compose run --rm -T heybox python --version
sudo docker compose run --rm -T heybox java -version
```

看到什么：Built 字样及 `Python 3.12.x`。首次拉取镜像可能需要数分钟。

下一步：测试微信通知。

## 6. 单独测试微信

在哪里：SSH。

输入：

```sh
sudo docker compose run --rm -T heybox python main.py --test-notify
```

看到什么：日志显示通知受理成功，微信收到“飞牛小黑盒签到测试”。该命令不执行签到。

下一步：微信确认收到后测试签到。

## 7. 测试签到

在哪里：SSH。

输入：

```sh
sudo docker compose run --rm -T heybox
```

看到什么：签到成功、今日已签到，或明确的失败原因；每种结果都会尝试微信通知。容器执行后消失是正常现象。

下一步：查看日志。维护者已在私人环境验证 v3 签到接口；若以后出现“非法请求”，核对移动端凭据/设备配置和服务端协议变化。

## 8. 设置每天 00:01

在哪里：SSH；本次若已经安装 cron，则先查看而不是重复新增。

输入：

```sh
sudo cat /etc/cron.d/heybox-checkin
sudo systemctl is-active cron
```

看到什么：计划行为 `1 0 * * * root ...`、cron 为 active。

新安装需要创建计划时输入：

```sh
sudo chmod 750 /vol1/docker/heybox-checkin/run.sh
sudo nano /etc/cron.d/heybox-checkin
```

填写三行（最后一行之后也按一次回车）：

```cron
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
1 0 * * * root /usr/bin/flock -n /run/lock/heybox-checkin.lock /vol1/docker/heybox-checkin/run.sh
```

保存退出，再输入：

```sh
sudo chown root:root /etc/cron.d/heybox-checkin
sudo chmod 644 /etc/cron.d/heybox-checkin
sudo systemctl is-active cron
```

看到什么：active。cron 自动读取配置，不必重启飞牛。

下一步：检查一次脚本入口；不要再设置第二份飞牛计划任务。

## 9. 检查任务入口与日志

在哪里：SSH。

输入：

```sh
sudo /usr/bin/flock -n /run/lock/heybox-checkin.lock /vol1/docker/heybox-checkin/run.sh
sudo tail -n 60 /vol1/docker/heybox-checkin/logs/last-run.log
sudo tail -n 60 /vol1/docker/heybox-checkin/logs/heybox.log
```

看到什么：最后一次容器输出与详细签到/通知结果。通知受理成功时在微信核对实际收件。

下一步：任务每天 00:01 自动启动一次；若凭据过期，按 README 更新 .env，再手动测试。
