"""
生成 PawLife TabBar 图标
使用 Pillow 绘制简洁可爱风格的 81x81 PNG 图标
"""
from PIL import Image, ImageDraw
import math
import os

OUTPUT_DIR = "/Users/aicer/pawlife/frontend/src/static/tabbar"
SIZE = 81
ACTIVE_COLOR = (255, 140, 105)  # #FF8C69 珊瑚橙
INACTIVE_COLOR = (140, 140, 140)  # #8C8C8C 灰色
BG_COLOR = (0, 0, 0, 0)  # 透明背景
LINE_WIDTH = 4


def create_canvas():
    """创建透明画布"""
    return Image.new("RGBA", (SIZE, SIZE), BG_COLOR)


def draw_rounded_rect(draw, bbox, radius, fill):
    """绘制圆角矩形"""
    x1, y1, x2, y2 = bbox
    r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    draw.rounded_rectangle(bbox, radius=r, fill=fill)


def draw_chat_icon(color):
    """对话气泡图标"""
    img = create_canvas()
    draw = ImageDraw.Draw(img)

    # 气泡主体
    bbox = [12, 10, 69, 52]
    draw.rounded_rectangle(bbox, radius=16, outline=color, width=LINE_WIDTH)

    # 气泡尾巴（三角形）
    tail = [(28, 52), (22, 66), (40, 52)]
    draw.polygon(tail, fill=None, outline=color)
    # 覆盖尾巴与气泡交界处的多余线条
    draw.line([(28, 52), (40, 52)], fill=color, width=LINE_WIDTH)

    # 三个小点表示对话
    cx = 40
    cy = 31
    for dx in [-12, 0, 12]:
        bbox_dot = [cx + dx - 3, cy - 3, cx + dx + 3, cy + 3]
        draw.ellipse(bbox_dot, fill=color)

    return img


def draw_timeline_icon(color):
    """时间线/记录图标 - 时钟 + 线条"""
    img = create_canvas()
    draw = ImageDraw.Draw(img)

    # 时钟外圈
    cx, cy, r = 40, 34, 22
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, outline=color, width=LINE_WIDTH)

    # 时钟指针
    # 时针（短）
    draw.line([(cx, cy), (cx, cy - 13)], fill=color, width=LINE_WIDTH)
    # 分针（长，倾斜）
    draw.line([(cx, cy), (cx + 10, cy + 4)], fill=color, width=LINE_WIDTH)
    # 中心点
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=color)

    # 底部三条记录线
    y_base = 66
    for i, w in enumerate([30, 22, 14]):
        x_start = 26
        bbox_line = [x_start, y_base + i * 6, x_start + w, y_base + i * 6 + 3]
        draw.rounded_rectangle(bbox_line, radius=1, fill=color)

    return img


def draw_profile_icon(color):
    """宠物管理图标 - 爪印"""
    img = create_canvas()
    draw = ImageDraw.Draw(img)

    cx, cy = 40, 40

    # 大肉垫（椭圆）
    pad_w, pad_h = 22, 18
    bbox_pad = [cx - pad_w // 2, cy + 2, cx + pad_w // 2, cy + 2 + pad_h]
    draw.ellipse(bbox_pad, fill=color)

    # 四个小肉垫
    toe_r = 8
    toes = [
        (cx - 14, cy - 8),   # 左下
        (cx - 8, cy - 18),   # 左上
        (cx + 8, cy - 18),   # 右上
        (cx + 14, cy - 8),   # 右下
    ]
    for tx, ty in toes:
        bbox_toe = [tx - toe_r, ty - toe_r, tx + toe_r, ty + toe_r]
        draw.ellipse(bbox_toe, fill=color)

    return img


def draw_account_icon(color):
    """账户图标 - 人形 + 设置齿轮"""
    img = create_canvas()
    draw = ImageDraw.Draw(img)

    cx = 34

    # 人头（圆）
    head_r = 10
    bbox_head = [cx - head_r, 12, cx + head_r, 12 + head_r * 2]
    draw.ellipse(bbox_head, fill=color)

    # 人身（半椭圆/弧形）
    body_bbox = [cx - 18, 34, cx + 18, 56]
    draw.pieslice(body_bbox, start=180, end=360, fill=color)

    # 右侧齿轮（简化的圆+线）
    gx, gy, gr = 62, 44, 10
    draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], outline=color, width=LINE_WIDTH)
    # 齿轮中心
    draw.ellipse([gx - 3, gy - 3, gx + 3, gy + 3], fill=color)
    # 四个齿
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        x1 = gx + int((gr - 2) * math.cos(rad))
        y1 = gy + int((gr - 2) * math.sin(rad))
        x2 = gx + int((gr + 4) * math.cos(rad))
        y2 = gy + int((gr + 4) * math.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=3)

    return img


def save_icon(img, filename):
    """保存图标"""
    path = os.path.join(OUTPUT_DIR, filename)
    img.save(path, "PNG")
    size = os.path.getsize(path)
    print(f"  {filename}: {size} bytes")


def main():
    print("Generating PawLife TabBar icons (81x81px)...")

    icons = [
        ("chat", draw_chat_icon),
        ("timeline", draw_timeline_icon),
        ("profile", draw_profile_icon),
        ("account", draw_account_icon),
    ]

    for name, draw_func in icons:
        # 普通态（灰色）
        img_normal = draw_func(INACTIVE_COLOR)
        save_icon(img_normal, f"{name}.png")

        # 激活态（珊瑚橙）
        img_active = draw_func(ACTIVE_COLOR)
        save_icon(img_active, f"{name}-active.png")

    print("Done!")


if __name__ == "__main__":
    main()
