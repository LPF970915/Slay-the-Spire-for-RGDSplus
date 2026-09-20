# P0 单屏验证

本文件保留早期启动与冒烟测试范围。完整阶段划分、单屏完成门禁和双屏方案
以 [完整移植计划](RGDSPLUS_PORT_MASTER_PLAN.zh-CN.md) 及
[验收台账](RGDSPLUS_ACCEPTANCE_MATRIX.zh-CN.md) 为准。
通过本文的短流程不等于单屏完全适配。

目标是先在 RGDSplus 上稳定运行《杀戮尖塔》桌面版移植，不做双屏 UI 拆分。

## 运行边界

- 一个 Java 进程、一个游戏规则状态和一个存档目录。
- 逻辑与窗口均为 `1024x768`。
- 使用 PortMaster Weston wrapper runtime 提供 XWayland/GL4ES 兼容窗口。
- 不改动 `desktop-1.0.jar`，不删除正版原件。
- 补丁输出写入 `cache/builds/<源文件哈希>-<构建版本>/`，完成后原子提交。
- 第一阶段不启用 ModTheSpire、BaseMod 或其它玩法 Mod。
- 不修改 DT、udev、Weston 配置和固件触摸硬件。

## 首次启动验收

按顺序记录：

1. 冷启动耗时、补丁耗时、标题画面和音频。
2. 新建一局，进入战斗，打出攻击牌、防御牌和能力牌。
3. 结束回合、敌人行动、获得奖励并进入地图。
4. 进入商店、事件、营火和首领战。
5. 保存退出，重新启动并读档。
6. 连续运行至少 30 分钟，记录 Java RSS、高峰 RSS、系统
   `MemAvailable`、线程数和是否出现内核 OOM。
7. 正常退出并回到前端；再次启动确认存档仍可用。

## 日志

安装目录下：

- `logs/latest-path.txt`：最近主日志路径。
- `logs/<session>.log`：启动参数、补丁和 Java 输出。
- `logs/<session>.resources.log`：每 10 秒的进程与系统资源。
- `logs/<session>.crash.txt`：非零退出时的尾部日志和内核信息。

首次补丁可能较慢。上游提示约 15 分钟，这是补丁阶段耗时，不应直接
当作游戏启动卡死。若超过预期，应先查看主日志和资源日志。

## 失败分类

- 找不到 Java 17 运行时：检查 PortMaster runtime 是否安装。
- 找不到 `xdelta3`、`python3` 或音频工具：检查 PortMaster 工具链。
- 补丁失败：保留 `desktop-1.0.jar`，删除未完成的临时缓存后重试。
- Java 启动但无窗口：保留日志，先检查 Weston wrapper、X11 兼容库和图形依赖，
  不要立刻改成双屏或扩大堆上限。
- 游戏能启动但场景崩溃：记录场景、存档状态、Java 日志和 RSS，
  禁止用 Mod 框架掩盖基础运行时问题。
