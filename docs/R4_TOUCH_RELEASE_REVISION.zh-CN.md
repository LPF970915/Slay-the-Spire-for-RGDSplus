# 2026-09-23 触摸释放、教程与窗口修复

构建：`r4-interface-20260923-9`。
分发：`Slay the Spire for RGDSplus`，只含适配层。

## 故障与修复

- 事件界面按键可响应，触摸桥存在 `down-hit=true`，但原生事件未提交。
  事件选项移到下屏后，释放阶段必须把坐标恢复到原生 Hitbox 空间。
  最终抬起坐标仍须命中本帧可见下屏目标，不能无条件把滑出的手指吸附回按钮。
- `MultiPageFtue` 覆盖基类渲染，需独立下屏路由。教程临时使用同一个
  `ProceedButton`，现在由教程独占其触摸提交，阻止普通继续逻辑打开地图。
  原生教程遮罩也限制到下屏。教程期间不激活手牌控制器焦点。
- `DynamicBanner` 下屏绘制，删除奖励页上屏的额外摘要。
- 资源提示保留跨补丁/游戏阶段的 PID，只创建一个实例，并绑定启动器生命周期。
  首帧出现自动结束提示，退出路径统一清理提示及观察进程。
- Windows 部署工具明确以 UTF-8 读取带中文提示的启动脚本。

## 验证边界

全部游戏实验使用 `/mnt/sdcard/Ports/SlayTheSpireDualR4Review`。
未用正式用户存档进行场景注入。测试存档另行归档；不覆盖稳定单屏运行时。

已有证据：

- `validation/r4-review/interfaces-tutorial-1790129771144275200.json`：
  空白测试存档首次开局，触摸逐页推进至战斗，第一张牌未悬浮且保留扇形角度。
- `validation/r4-review/interfaces-events-1790129891736542100.json`：
  滑出、多指、B 接管均未提交；正常选择最大生命 +5 生效一次，离开可进地图。
- `validation/r4-review/interfaces-rewards-1790129997077856000.json`：
  卡牌先预览再确认，永久牌组增加一张；金币奖励增加 25。
- 资源提示强制显示后已退出，生成 `.ready`，首帧后无提示终端进程。
- 最终候选二次空白存档复测：
  `validation/r4-review/interfaces-tutorial-1790131184805952600.json`。
  `revision9-final-tutorial-stacked.png` 显示上屏不再覆盖教程遮罩。
- `revision9-final-u17-stacked.png`、`revision9-final-u18-stacked.png`、
  `revision9-final-u19-stacked.png`：奖励横幅与选择在下屏；
  卡牌/遗物的选中详情仍保留上屏，只读。
- 编译覆盖 99 个原生类及原生/控制器/适配器变换顺序；
  39 项 R4 回归、34 项 P1 测试、触摸生命周期契约通过。
- 同一最终构建的事件/奖励复测分别见
  `interfaces-events-1790131490825043300.json`、
  `interfaces-rewards-1790131666699261400.json`。
- 正式目录有声启动约两分钟后按测试超时退出，没有进入用户存档。
  `validation/r4-all-pages/20260923-025405-18563.log` 记录提示启动、
  首帧完成、菜单稳定运行及测试退出；存在原有日志格式与 locale 警告，
  未出现适配器类变换失败。
- `validation/r4-all-pages/audit-1790132541674260046.json`：
  正式/review 锁均 free，触摸模式恢复为启动前的 0，仅系统 Weston 和菜单仍运行。
  旧单屏目录的三个参考文件在设备上缺失，审计明确记录，不推断为已验证。
  `revision9-notice-exit.json` 确认提示终端/脚本进程无残留。

这些是 evdev 注入、游戏诊断及 framebuffer 证据，不是实体触摸准确度、
物理面板排列或真实声音的验收。最终实体触摸与屏幕观感仍由用户确认。
没有宣称自然完成整局或所有随机事件已经遍历。
