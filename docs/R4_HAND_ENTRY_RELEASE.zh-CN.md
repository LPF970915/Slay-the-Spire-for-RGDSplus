# R4 入场手牌与内部测试包

日期：2026-09-21。当前构建：`r4-hand-entry-20260921-3`。

## 入场手牌

首次进入房间时，原生手柄路径会自动悬停第一张牌，导致它竖直抬起。
新增 `HandFocus` 记录房间及手柄按下边沿：没有新操作时保持自然扇形，
新的真实手柄按下仍可接管原生选牌；从菜单持续按住的旧按键不作为新选牌。
复用原生 `releaseCard` / `refreshHandLayout`，不手工设置扇形角度，
不跳过待结束回合和敌方回合的原生处理。

用户在本轮明确反馈“已经手动确认都好了”，随后要求直接部署和制作多人测试包。
此处记录用户实体确认，不扩写为定量精度、全卡牌、全流程或长稳验收。
用户确认后未继续战斗注入。

## 部署

- 卡二目录仍为 `/mnt/sdcard/Ports/SlayTheSpireDualR4`。
- 入口仍为 `Slay the Spire R4 All Pages.sh`。
- 默认有声、真实下屏触摸、30 FPS；不使用 `--silent`，不改个人音量偏好。
- 适配器 SHA256：
  `b37876451b804d6c01fc19e8520c470830e94c192a0f3d93701005def38cd7d7`。
- 双屏 SDL SHA256：
  `5bdff69d797d009c5a43f2dc3223aa77f7610ea2029e893d337b81807e097f25`。
- 13 个运行文件与部署 manifest 全部匹配。
- 104 项单屏/R3/R4 存档、设置、战绩及稳定单屏文件在部署前后校验一致。
- 旧运行文件、旧入口及保护清单保存在私有目录
  `validation/r4-all-pages/hand-entry-deployment-1789965275133756100/`。

## 内部包

本次内部验证曾使用私有打包工具（不随公开仓库发布），
需显式传入 `--private-authorized-test` 和本地正版原件，不改变公共无资源打包器。
它从已校验部署按白名单取运行文件、补丁缓存及 Java/Weston 镜像，
不递归复制玩家目录。个人 saves、betaPreferences、runs、logs、凭据均禁止入包。

包内入口仅增加独立 `SLAYTHESPIRE_PORTMASTER` 指向：
`SlayTheSpireDualR4/runtime/PortMaster`。本机普通入口保持原样。
未覆盖全局 PortMaster、稳定单屏或固件，测试包仍依赖兼容 RGDSplus 系统库。
携带 939 个已验证的纯资源纹理缓存，不含玩家状态。
未缓存的新场景仍可能首次较慢，冷场景与热场景测试应分开记录。

本地交付：

- `dist/SlayTheSpire_RGDSplus_R4_20260921-3_PRIVATE_with_game_cached.zip`
- `dist/SlayTheSpire_RGDSplus_R4_20260921-3_PRIVATE_with_game_cached.zip.sha256`
- 大小 863,116,232 字节，约 823 MiB。
- ZIP SHA256：
  `3779145ddcd3c0ca63e7c381a781527d59987b8ee357623437dabf53f5dabfd1`。
- 包内 993 个载荷文件及独立 manifest / checksums，逐文件读回校验通过。
- 本地正版原件 SHA256：
  `cfad868ac8d65a88e71a0bf096fb09f78811e553effe0787c5309a655e081673`。

这是用户明确要求的授权内部测试包，不是公开发布包。
游戏本体、设备依赖、私有压缩包及证据不提交 Git、不上传公开仓库。
测试人员使用全新测试存档；安装说明及反馈模板见
公开包说明见 `packaging/R4_ADAPTER_ONLY.zh-CN.md`。

## 软件门禁

- Java 构建及 96 类转换、真实三 agent 链、HandFocus 单元测试通过。
- tools unittest 49 项、P1 unittest 34 项通过。
- 触摸生命周期契约、R3 契约、公共无游戏资源检查通过。
- 公共检查对备份里的同名双屏适配 JAR 同样核验仅有 `rgds/` / `META-INF/`，
  不再仅允许构建目录的一个位置；没有放宽正版资源排除规则。
- 测试包没有夹带个人进度，声音由普通默认入口启用。

包的空存档启动检查单独记录，不能代替用户实际游玩或长稳验收。
首份无纹理缓存的候选包在 120 秒内仍进行 ASTC 压缩，未到菜单；
已退出、保存证据并弃用该候选，未把等待超时当作通过。
证据：`validation/r4-all-pages/r4-package-smoke-1789965708293909800/`。

最终带缓存包的独立启动检查通过：

- 在新建隔离目录重建包内全部 993 个载荷文件，并逐个校验与 ZIP 一致；
  启动前没有 saves 或 betaPreferences，不继承玩家进度。
- 使用包内实际入口，加载包内 Java/Weston，成功到达 `MAIN_MENU`。
- 默认日志为 `audio=enabled touch=native-lower-pointer`，
  Java 音频流 `Corked: no`、`Mute: no`；这不是远程实体听感证明。
- 通过会话监护退出，`tpctrl before=0 -> active=0 -> restored=0`，
  无残留 Java、菜单恢复、会话锁全部释放。临时安装目录已清理。
- 再次核验 104 项原有文件，全部与部署前一致。
- 证据：`validation/r4-all-pages/r4-package-smoke-1789966470441825600/`、
  `validation/r4-all-pages/audit-1789966660630692562.json`。
- 最终设备停在系统菜单，等待用户启动普通 R4 入口，没有后台继续游玩。
