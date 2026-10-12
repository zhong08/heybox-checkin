# 原生签名模块构建

Java 源码使用 Unidbg 0.9.9，执行兼容 App 的 ARM64 库。JVM 最大堆 96 MB，输入仅包含路径、账号 ID 和设备元数据，Cookie 和微信密钥保留在 Python 中。

以下私人资源不随公开仓库分发，需要自行从本人兼容的 App 准备，放在此目录：

| 文件 | 内容 |
| --- | --- |
| libglesv3_1.so | App 1.3.385 的 ARM64 ShaderManager 原生库 |
| libnative-lib.so | 同一版本的 NDKTools ARM64 库 |
| app-metadata.apk | 同一 APK 的 manifest 和证书元数据 |
| shader-code.bin | 兼容的版本 14 初始化数据 |

对应设备的 DebugInfo 放在项目 `.env` 的 HEYBOX_DEBUG_INFO 中。此源码固定适配 Android 16 / App 1.3.385/build 1092。不同版本不能假设兼容。

安装 JDK 17+ 和 Maven 后，在项目根目录执行：

```sh
cd signer
mvn -B org.apache.maven.plugins:maven-dependency-plugin:3.8.1:copy-dependencies -DoutputDirectory="$PWD/lib"
mkdir -p .build
javac -encoding UTF-8 -cp 'lib/*' -d .build NativeSigner.java net/fornwall/jelf/ElfParser.java net/fornwall/jelf/ElfParserCheck.java
java -cp '.build:lib/*' net.fornwall.jelf.ElfParserCheck
jar --create --file native-signer.jar -C .build .
cd ..
```

生成的 JAR、依赖和私人资源留在本地，供 Docker COPY 使用。`.gitignore` 排除这些文件。不要复制整个私人部署目录上传。

ElfParser.java 来自 Unidbg 内置 JElf；byteSwap(long) 使用 Long.reverseBytes，修复 64 位高位地址丢失。回归检查与原许可证保留在仓库中。
