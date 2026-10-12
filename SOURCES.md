# 接口与依赖来源

核对日期：2026-10-12。这里记录公开实现的依据，不代表接口承诺长期稳定。

- 签到、任务列表及 Android 参数：原作者的抓包记录 https://github.com/wentaoabcd/QinglongCheckinScripts/blob/main/docs/heybox-api.md 。记录的接口为 `/task/sign_v3/sign`、`/task/list_v2/`；签到 state 为 success/ignore/fail。
- 扫码登录：MIT 项目 https://github.com/shadowfish07/heybox-cli ，文件 `internal/api/client.go`、`internal/auth/credential.go`。扫码创建和状态接口必须返回真实 qr_url 和凭据后才保存。
- 当前网页签名：MIT 项目 https://github.com/XiaHouSheng/heybox-core ，文件 `src/encoder_cli/process_origin.js`、`src/main/Net/builder.py`。Python 移植与原 JavaScript 三组输入的结果一致；真实账号 `/task/list_v2/` 返回 status=ok。项目只使用 Python 标准库实现，无 Node.js 运行依赖。
- Server酱官方 Python 文档：https://sct.ftqq.com/docs/integrations/python/ 。SCT 与 sctp 两种端点及 code=0 受理条件均来自官方示例。
- PushPlus 官方消息文档：https://pushplus.plus/doc/guide/api.html 。使用 HTTPS POST，code=200 表示服务受理，不代表微信终端必然收到。
- requests 2.32.5：https://pypi.org/project/requests/2.32.5/ ，支持 Python 3.9+（包含 3.12）。
- python-dotenv 1.2.1：https://pypi.org/project/python-dotenv/1.2.1/ ，支持 Python 3.9+（包含 3.12）。本项目已在 Python 3.12.14 安装验证。

本次真实测试：已授权的本人 Root 手机 App 1.3.385（build 1092）日志确认 v3 签到路径及真实 Android 参数；APK 中 Retrofit 注解也确认同一路径。网页签名被拒绝，因此日常签到使用原生签名：`com.graphice.shaderar.ShaderManager` / `libglesv3_1.so`，配合 `libnative-lib.so`；初始化数据来自本人 App 的 gles30 缓存，版本 14。库没有被补丁修改。独立进程计算 `_time`、`nonce`、8 位 `hkey` 和 `_rnd` 后，请求签到端点得到 `status=ok, result.state=ignore`。这证明提交端点接受新版签名；今天已签到，不声称本次新增奖励。旧 `/task/sign/` 返回 HTTP 404，未作回退。

原生执行框架使用 Unidbg 0.9.9（Apache-2.0）：https://github.com/zhkl0228/unidbg 。仅模拟签名库需要的 ARM64/JNI 环境，不启动完整 Android。JElf 来源：https://github.com/fornwall/jelf （MIT）；修复 Unidbg 内置 ElfParser 的 64 位字节交换符号扩展错误，改用 `Long.reverseBytes`，保留源码和可运行回归检查。原 APK 只保留 manifest 和证书元数据供框架读取；登录凭据始终在 .env 中。

当前原生参数固定为 App 1.3.385/build 1092、Android 16，与已验证的本人请求一致。若服务端更新协议或登录凭据失效，程序会明确通知失败/登录失效，需要重新适配或更新凭据。

程序直接提交 v3 签到；state=success/ignore 分别对应“签到成功/今日已签到”，拒绝响应如实通知失败。随后查询同样来自本人 App 日志的 `/task/sign_v3/get_sign_state`，读取 sign_in_exp、sign_in_coin、sign_in_streak、level_info.level。未确认提交 state=success/ignore 时，绝不仅因 status=ok 就宣布成功。`/task/list_v2/` 在新版移动会话下拒绝请求，已从日常执行链路移除。

奖励显示为服务器今日记录，不将重复签到时查询到的奖励声称为本次新增。公开仓库不包含私人验证记录、原始请求、App 二进制或初始化数据。
