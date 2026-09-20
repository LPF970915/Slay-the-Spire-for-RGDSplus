"""Build a local-only review gallery from actual captured framebuffers."""

import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/r4-review"
TITLES = [
    "启动与章节过场", "主菜单", "档位与命名", "角色选择", "自定义模式", "涅奥对话",
    "地图", "战斗与手牌", "卡牌选敌", "战斗动画", "战斗信息检视", "药水菜单",
    "牌组与牌堆", "手牌选择", "升级与网格选择", "临时三选一", "战斗奖励",
    "卡牌奖励", "首领遗物", "商店", "事件", "营火", "宝箱", "顶部栏检视",
    "卡牌详情", "设置", "确认与模态弹窗", "死亡与结算", "图鉴", "统计与历史",
    "制作名单与说明", "在线入口", "兼容显示示例",
]


def main():
    captures = json.loads((OUT / "captures.json").read_text(encoding="utf-8"))
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    sections, nav = [], []
    count = 0
    for group in range(3):
        sheet = Image.new("RGB", (1040, 1272), "#e8e9eb")
        draw = ImageDraw.Draw(sheet)
        for cell in range(11):
            number = group * 11 + cell + 1
            scene = f"u{number:02}"
            title = f"{scene.upper()} {TITLES[number - 1]}"
            entry = captures.get(scene, {})
            x, y = (cell % 4) * 260, (cell // 4) * 424
            draw.text((x + 10, y + 8), title, font=font, fill="#17191c")
            image_path = OUT / entry.get("image", "missing")
            if image_path.is_file():
                with Image.open(image_path) as original:
                    assert original.size == (1024, 1536), image_path
                    image = original.convert("RGB").resize((240, 360), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + 10, y + 38))
                status = "原生 UI 测试场景"
                count += 1
                media = f'<a href="{html.escape(image_path.name)}"><img width="1024" height="1536" src="{html.escape(image_path.name)}" alt="{title}"></a>'
            else:
                status = "未采集，不以其他页面替代"
                media = '<p class="missing">未取得有效截图</p>'
            draw.text((x + 10, y + 402), status, font=small, fill="#3e454b")
            nav.append(f'<a href="#{scene}">{scene.upper()}</a>')
            details = html.escape(entry.get("note", ""))
            sections.append(f'<section id="{scene}"><h2>{title}</h2><p>{status} · {details}</p>'
                            f'{media}<p class="meta">{html.escape(entry.get("build", ""))} '
                            f'· 原生状态 {html.escape(entry.get("page", ""))}</p></section>')
        sheet.save(OUT / f"overview-{group + 1}.png")
    document = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RGDSplus 双屏界面对照</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f2f3;color:#202326;font:16px "Microsoft YaHei",sans-serif;letter-spacing:0}}
header{{padding:24px 28px;background:#fff;border-bottom:1px solid #cdd1d4}}
h1{{font-size:26px;margin:0 0 10px}}p{{line-height:1.6}}nav{{display:flex;flex-wrap:wrap;gap:12px;padding:12px 28px;background:#fff}}
a{{color:#17684e}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:30px;padding:28px}}
section{{min-width:0;border-top:2px solid #b9c2c7;padding-top:12px;scroll-margin-top:16px}}
h2{{font-size:20px;margin:0}}section img{{width:100%;height:auto;display:block;max-width:640px}}
.meta{{color:#62696f;font-size:13px}}.missing{{min-height:240px;background:#e0e3e5;padding:24px}}
@media(max-width:600px){{main{{padding:12px}}header{{padding:18px}}}}
</style><header><h1>RGDSplus 双屏界面对照</h1>
<p>2026-09-20 · {count}/33 个界面族已有截图 · 静音测试 · 每屏 1024×768</p>
<p>设备 framebuffer 上下拼接，非屏幕实拍。隔离原生 UI 测试场景不代表自然流程、实体触控或全分支验收。
U10 为原生动画特效样例；U28 为测试结算；U32 不代表在线服务可用；U33 为兼容页面示例。</p>
<p><a href="overview-1.png">U01–U11 总览</a> · <a href="overview-2.png">U12–U22 总览</a> ·
<a href="overview-3.png">U23–U33 总览</a></p></header><nav>{''.join(nav)}</nav><main>{''.join(sections)}</main></html>"""
    (OUT / "index.html").write_text(document, encoding="utf-8")
    print(f"{count}/33 captured; {OUT / 'index.html'}")


if __name__ == "__main__":
    main()
