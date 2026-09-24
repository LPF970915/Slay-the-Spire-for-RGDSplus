# Slay the Spire for RGDSplus

RGDSplus 双屏适配项目，移植维护：**Blood_roc**。

> **本仓库及 Releases 仅发布适配包，不包含《杀戮尖塔》游戏本体。**
> 请购买正版 Steam/PC 版本，并自行提供合法取得的 `desktop-1.0.jar`。
> 本项目不提供破解、盗版、授权绕过、Steam 凭据或完整游戏资源。

这是面向 RGDSplus 双 1024×768 屏幕、Linux/Wayland 固件、PortMaster
环境的非官方适配项目。它不是 Mega Crit 或 Steam 的官方发行版。

## 下载

从 [GitHub Releases](https://github.com/LPF970915/Slay-the-Spire-for-RGDSplus/releases)
下载正式命名的 `Slay the Spire for RGDSplus.zip`。

Release 附件是适配包，不是游戏本体，也不是 GitHub 自动生成的
“Source code”压缩包。发布包旁提供 `.sha256` 校验文件。

## 安装

1. 退出游戏，升级前备份内存卡上的 `saves/`。
2. 将压缩包解压到卡二游戏数据分区根目录，合并 `Ports`，不要形成
   `Ports/Ports/`。
3. 从正版 PC 安装目录复制 `desktop-1.0.jar` 到：

   ```text
   /mnt/sdcard/Ports/Slay the Spire for RGDSplus/
   ```

4. 从 Ports 菜单启动 **Slay the Spire for RGDSplus**。

目录结构：

```text
Ports/
  Slay the Spire for RGDSplus.sh
  Slay the Spire for RGDSplus/
    game-launch.sh
    desktop-1.0.jar        <- 用户自行提供，发布包不包含
    runtime/offline/       <- 包内 Java 17 和 Weston，无需联网下载
    cache/
    saves/
    logs/
```

首次启动会从正版 JAR 生成隔离的补丁 JAR 和纹理缓存。释放资源期间会显示
阶段、计数和心跳信息；请勿断电或拔卡。原始正版文件不会被覆盖，失败时可
删除未完成的 `cache/` 后重试。后续启动会复用已完成缓存。

`20260924-02` 起内置 ARM64 Java 17 和 Weston 离线镜像，安装方法与视频一致：
复制整个 `Ports` 到卡根目录，再放入正版 JAR；不需要打开 PortMaster 下载依赖。
启动器优先使用游戏目录内的镜像，不修改共享 PortMaster，不依赖其他移植游戏。
包内同时附带所需的 ARM64 `libjpeg.so.8` 和 `libXtst.so.6`，
不再借用阅读器或其他游戏的库。
启动前显示离线运行库检查提示，校验文件完整性并实际测试 Java。
从旧版升级时完整覆盖适配文件即可，不需要删除正版文件、缓存或存档。
预检失败时会记录 `logs/*.preflight.txt`，显示服务可用时会留屏提示约 45 秒。
仍需使用兼容的 RGDSplus ARM64 固件及其自带的 PortMaster、Python 3、
Wayland 和系统音频库；离线包不替换固件及显卡驱动。

## 当前适配

- 上屏保留战斗、地图、角色、商人及主要演出；下屏承担手牌和操作区域。
- 教程、事件、奖励、商店购买、地图、牌组、遗物、药水和设置等页面按双屏
  交互规则分配。
- 下屏实体触摸使用设备本地坐标；保留手柄导航和独立应急退出。
- 事件触发战斗使用与普通战斗一致的扇形手牌和双屏布局。
- 资源释放、补丁、纹理缓存和启动失败会写入日志，并显示可观察的进度。

本版本仍是测试发布。全流程、所有机制、实体触摸精度、不同固件兼容性和
长期稳定性尚未全部验收；软件注入、回放和截图不能替代真实触摸验证。

## 更新与反馈

更新前退出游戏并备份整个 `saves/`。保留正版 JAR、存档和日志，只替换
适配文件。反馈问题时请注明版本、固件、输入来源、复现步骤和日志时间，
并先脱敏。不要上传正版游戏文件、派生 JAR、缓存、账号信息或未经检查的存档。

## 开发构建

构建适配器需要用户本机已有的正版 JAR；脚本不会下载或提交游戏本体：

```powershell
$env:STS_GAME_JAR = "D:\path\to\desktop-1.0.jar"
$env:JAVA_HOME = "C:\Program Files\Java\jdk-25"
py -3 prototype/r3/build.py
py -3 -m pip install zstandard
py -3 tools/fetch_offline_runtimes.py
py -3 tools/assemble_r4_adapter_package.py
py -3 tools/test_touch_contract.py
py -3 -m unittest discover -s prototype/p1 -v
```

构建输出 `dist/Slay the Spire for RGDSplus.zip`，适配包审计会拒绝游戏本体、
存档、缓存、日志和凭据。

## 发布与权利声明

本人仅通过本仓库及其 Releases 公开发布不含游戏本体的适配包。未经授权，
不得将本项目、作者署名或项目名义用于收费售卖、付费预装、商业整合包或
冒充官方服务。原创适配部分的使用范围见 [LICENSE.md](LICENSE.md)。

PortMaster 及其他第三方组件继续适用各自许可证；详见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目与游戏权利人不存在
官方隶属、授权背书或合作关系。

## 项目结构

```text
docs/       设计、触摸契约、适配说明与验收边界
packaging/  公开启动器、安装说明和第三方声明
platform/   RGDSplus 输入与安全补丁组件
prototype/  P1 触摸参考链路与 R3 双屏适配实现
tools/      构建、打包、测试和公开载荷审计工具
```
