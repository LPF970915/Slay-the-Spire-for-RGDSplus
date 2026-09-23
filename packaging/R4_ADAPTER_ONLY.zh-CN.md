# Slay the Spire for RGDSplus

适配包版本：`20260923-14`

这是不含正式游戏本体的公开适配包。请先拥有合法购买的 Steam 版本，
再只把正版文件 `desktop-1.0.jar` 复制到游戏目录。
`/mnt/sdcard/Ports/` 下的菜单脚本和游戏目录使用同一个正式名称：

```text
/mnt/sdcard/Ports/Slay the Spire for RGDSplus.sh
/mnt/sdcard/Ports/Slay the Spire for RGDSplus/desktop-1.0.jar
```

不要复制 `SlayTheSpire.exe`、Windows `jre/`、`mod-uploader.jar`、
`mts-launcher.jar`，也不要把个人 `saves/`、`betaPreferences/`、`logs/`
放进发布包。适配包只提供双屏适配器、输入链、启动脚本和 PortMaster
所需的公开依赖；游戏资源由用户自己的正版 JAR 提供。

## 安装

1. 退出掌机上正在运行的游戏，并确认固件支持 ARM64、PortMaster、Python 3、
   Weston、Java 17 和 `gt9xx-0` 触摸设备。
2. 将压缩包中的 `Ports` 合并到卡二根目录，不要多套一层目录。
   已有 `SlayTheSpireDualR4` 时，把整个目录改名为
   `Slay the Spire for RGDSplus`，不要另拷一份，以免存档分开。
3. 将自有正版 `desktop-1.0.jar` 放入上面的游戏目录。
4. 在 Ports 菜单启动 `Slay the Spire for RGDSplus`。

首次启动会从正版 JAR 生成隔离的 `cache/builds/` 衍生 JAR。释放资源期间
屏幕会显示“正在释放资源”，并显示当前阶段和音频文件计数；数据持续变化表示
没有卡死。只有补丁 JAR 通过完整性检查并提交 `ready.txt` 后才会启动游戏。
原始正版文件
不会被替换，失败时删除未完成的临时目录后可重试。Java 17 和 Weston
运行镜像默认由 PortMaster 提供；包内不覆盖系统运行时。

全新安装还需要在进入菜单前生成 `cache/texcache/` 纹理缓存，不能用带有
预热缓存的私有测试包估算首次等待时间。补丁阶段上游提示可能约需 15 分钟，
随后纹理压缩另需时间；后续启动会复用已完成的缓存。
排障时查看 `logs/latest-path.txt` 指向的日志：持续出现
`[patch]` 阶段进展或 `ASTC: compression succeeded` 表示仍在处理；
`missing tool`、`patch failed` 或 `launcher_exit` 则需要检查失败原因。
包内补丁工具的正确位置是 `Slay the Spire for RGDSplus/tools/xdelta3`，
不是游戏根目录；不要通过修改固件或永久系统 PATH 绕过安装问题。

默认配置为有声、30 FPS、双屏布局和下屏实体触摸。声音、显示、触摸模式的
生命周期由本次游戏会话独立管理；正常退出、启动失败和独立 Select 长按退出
都会恢复此前的触摸模式。不要修改固件校准或写死 event 编号。

## 测试重点

- `20260923-14` 修复事件触发战斗时错误回退到单屏手牌缩放；事件战斗现在使用普通战斗的双屏扇形手牌布局；
- 保留商人整套演出、奥涅预热对象坐标和首次进入过渡阶段的资源驻留预热；
- 保留上一版 UI/VFX 分帧预热、资源释放进度、心跳和纹理缓存复用；
  同时保留商店商品下屏触摸购买和本轮场景初始化性能采样。
- 首次教程的内容、遮罩和继续按钮均在下屏；教程退出后手牌不自动选中第一张。
- 战斗奖励、卡牌奖励和首领奖励的横幅在下屏，不再额外绘制上屏奖励摘要。
- 事件按钮抬起时必须仍命中有效目标；滑出、多指及手柄接管取消，不应提交选项。
- 初次进入战斗时手牌是否自然落入扇形。
- 下屏拖牌向上锁定最近敌人，左右滑动切换目标，继续向上只改变曲率。
- 拖回原始手牌位置或更低区域取消；在其上方松手按原生规则出牌。
- 黄色目标标识在上屏敌人本体，虚线、能量、牌堆、回合按钮和特效归属正确。
- 卡牌从下屏跨屏飞向上屏目标并逐渐缩小；触摸下屏时上屏不显示无用鼠标箭头。
- 药水、地图、奖励、事件、营火、牌组、遗物、设置和返回路径。
- 有声连续运行、冷启动/热启动、正常退出、长按 Select 应急退出。

软件注入、evdev 回放和 framebuffer 截图只能证明对应的软件链路，
不能替代实体触摸精度、屏幕面板顺序或真实声音体验。反馈时请注明设备、
固件、测试时长、输入来源和是否为实体操作。

## 完整性

压缩包旁的 `.sha256` 校验整个 ZIP。包内 `PACKAGE_MANIFEST.json` 列出适配
载荷的 SHA256，并明确 `game_assets_in_adapter=false`。发布包不包含正式
游戏 JAR、派生游戏 JAR、个人存档、缓存、日志或凭据。
