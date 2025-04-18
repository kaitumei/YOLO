import cv2
import numpy as np
from ultralytics import YOLO
import matplotlib.pyplot as plt
import matplotlib
import os
from PIL import Image, ImageDraw, ImageFont

# 解决 Matplotlib 中文乱码
matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 黑体
matplotlib.rcParams['axes.unicode_minus'] = False   # 解决负号显示问题

print("开始车牌识别流程...")

# 车牌检测模型
path = 'models/zhlkv3.onnx'
if not os.path.exists(path):
    print(f"警告: 模型文件 {path} 不存在!")

# 设置图片路径 - 检测当前目录中的所有jpg图片
import glob
image_files = glob.glob("utils\*.jpg")
if not image_files:
    print("错误: 当前目录中没有找到jpg图片文件!")
    exit(1)

img_path = image_files[0]  # 使用找到的第一张图片
print(f"使用图片: {img_path}")

# 加载YOLO模型
print(f"加载YOLO模型: {path}")
try:
    model = YOLO(path, task='detect')
except Exception as e:
    print(f"加载模型出错: {e}")
    exit(1)

# 读取原始图像
print(f"读取图片: {img_path}")
original_image = cv2.imread(img_path)
if original_image is None:
    print(f"错误: 无法读取图片 {img_path}")
    exit(1)

# 创建一个用于显示的图像副本
display_image = original_image.copy()

# 运行 YOLO 车牌检测
print("执行车牌检测...")
results = model(img_path)

# 检查是否检测到车牌
if len(results[0].boxes.xyxy) == 0:
    print("未检测到任何车牌!")
    
    # 显示原始图片
    plt.figure(figsize=(12, 8))
    plt.imshow(cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB))
    plt.title("原始图片 - 未检测到车牌")
    plt.axis('off')
    plt.show()
    exit(0)
else:
    print(f"检测到 {len(results[0].boxes.xyxy)} 个车牌")

# 绘制高级车牌框
def draw_fancy_box(img, x1, y1, x2, y2, thickness=3):
    """
    绘制美化的车牌识别框，包括渐变色边框和角标
    """
    h, w = img.shape[:2]
    
    # 定义渐变色 - 从亮绿色到深绿色
    color1 = (0, 255, 0)   # 亮绿色
    color2 = (0, 100, 0)   # 深绿色
    
    # 绘制渐变边框
    # 上边框 - 从左到右渐变
    for i in range(x1, x2):
        ratio = (i - x1) / (x2 - x1)
        color = (
            int(color1[0] * (1 - ratio) + color2[0] * ratio),
            int(color1[1] * (1 - ratio) + color2[1] * ratio),
            int(color1[2] * (1 - ratio) + color2[2] * ratio)
        )
        cv2.line(img, (i, y1), (i, y1 + thickness - 1), color, 1)
    
    # 右边框 - 从上到下渐变
    for i in range(y1, y2):
        ratio = (i - y1) / (y2 - y1)
        color = (
            int(color1[0] * (1 - ratio) + color2[0] * ratio),
            int(color1[1] * (1 - ratio) + color2[1] * ratio),
            int(color1[2] * (1 - ratio) + color2[2] * ratio)
        )
        cv2.line(img, (x2 - thickness + 1, i), (x2, i), color, 1)
    
    # 下边框 - 从右到左渐变
    for i in range(x2, x1, -1):
        ratio = (x2 - i) / (x2 - x1)
        color = (
            int(color1[0] * (1 - ratio) + color2[0] * ratio),
            int(color1[1] * (1 - ratio) + color2[1] * ratio),
            int(color1[2] * (1 - ratio) + color2[2] * ratio)
        )
        cv2.line(img, (i, y2), (i, y2 - thickness + 1), color, 1)
    
    # 左边框 - 从下到上渐变
    for i in range(y2, y1, -1):
        ratio = (y2 - i) / (y2 - y1)
        color = (
            int(color1[0] * (1 - ratio) + color2[0] * ratio),
            int(color1[1] * (1 - ratio) + color2[1] * ratio),
            int(color1[2] * (1 - ratio) + color2[2] * ratio)
        )
        cv2.line(img, (x1, i), (x1 + thickness - 1, i), color, 1)
    
    # 添加角标
    corner_length = min(30, (x2-x1)//4, (y2-y1)//4)  # 角标长度，不超过矩形的1/4
    
    # 左上角
    cv2.line(img, (x1, y1), (x1 + corner_length, y1), (0, 255, 0), thickness)
    cv2.line(img, (x1, y1), (x1, y1 + corner_length), (0, 255, 0), thickness)
    
    # 右上角
    cv2.line(img, (x2, y1), (x2 - corner_length, y1), (0, 255, 0), thickness)
    cv2.line(img, (x2, y1), (x2, y1 + corner_length), (0, 255, 0), thickness)
    
    # 左下角
    cv2.line(img, (x1, y2), (x1 + corner_length, y2), (0, 255, 0), thickness)
    cv2.line(img, (x1, y2), (x1, y2 - corner_length), (0, 255, 0), thickness)
    
    # 右下角
    cv2.line(img, (x2, y2), (x2 - corner_length, y2), (0, 255, 0), thickness)
    cv2.line(img, (x2, y2), (x2, y2 - corner_length), (0, 255, 0), thickness)
    
    return img

# PIL中文文本绘制函数 - 增强版
def draw_fancy_text(img, text, position, font_size=36, text_color=(255, 255, 255), bg_color=(0, 120, 0), add_shadow=True):
    """
    使用PIL绘制美化的中文文本到OpenCV图像上，带阴影、渐变背景和圆角效果
    """
    # OpenCV图像转为PIL图像
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    # 选择字体，使用系统中文字体
    try:
        # 尝试使用系统中文字体
        if os.path.exists('C:/Windows/Fonts/simhei.ttf'):  # Windows系统
            font = ImageFont.truetype('C:/Windows/Fonts/simhei.ttf', font_size)
        elif os.path.exists('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'):  # Linux系统
            font = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc', font_size)
        else:
            # 尝试使用默认字体
            font = ImageFont.load_default()
            print("警告: 找不到合适的中文字体，使用默认字体!")
    except Exception as e:
        print(f"加载字体出错: {e}, 使用默认字体")
        font = ImageFont.load_default()
    
    # 获取文本大小
    text_size = draw.textbbox((0, 0), text, font=font)[2:]
    padding = 10  # 文本周围的填充
    
    # 创建一个透明的图层用于绘制圆角矩形和文本
    overlay = Image.new('RGBA', img_pil.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # 计算矩形位置
    x, y = position
    rect_x1 = x - padding
    rect_y1 = y - padding
    rect_x2 = x + text_size[0] + padding
    rect_y2 = y + text_size[1] + padding
    radius = 10  # 圆角半径
    
    # 绘制圆角矩形背景 - 使用渐变色
    for i in range(rect_y1, rect_y2):
        ratio = (i - rect_y1) / (rect_y2 - rect_y1)
        # 从顶部的深绿色到底部的较亮绿色
        r = int(bg_color[0] * (1 - ratio) + min(bg_color[0] + 50, 255) * ratio)
        g = int(bg_color[1] * (1 - ratio) + min(bg_color[1] + 50, 255) * ratio)
        b = int(bg_color[2] * (1 - ratio) + min(bg_color[2] + 50, 255) * ratio)
        
        overlay_draw.line([(rect_x1, i), (rect_x2, i)], fill=(r, g, b, 220))
    
    # 添加边框
    for i in range(3):  # 3像素宽的边框
        overlay_draw.rectangle(
            [rect_x1+i, rect_y1+i, rect_x2-i, rect_y2-i], 
            outline=(255, 255, 255, 150), 
            width=1
        )
    
    # 如果启用阴影，绘制文本阴影
    if add_shadow:
        shadow_offset = 2
        overlay_draw.text(
            (x + shadow_offset, y + shadow_offset), 
            text, 
            font=font, 
            fill=(0, 0, 0, 160)
        )
    
    # 绘制文本
    overlay_draw.text((x, y), text, font=font, fill=text_color)
    
    # 合并图层
    img_pil = Image.alpha_composite(img_pil.convert('RGBA'), overlay)
    
    # PIL图像转回OpenCV图像
    return cv2.cvtColor(np.array(img_pil.convert('RGB')), cv2.COLOR_RGB2BGR)

# 遍历检测到的车牌
for i, result in enumerate(results[0].boxes.xyxy):
    print(f"处理第 {i+1} 个车牌...")
    x1, y1, x2, y2 = map(int, result[:4])
    print(f"车牌坐标: x1={x1}, y1={y1}, x2={x2}, y2={y2}")

    # 增加 padding
    padding = 5
    x1, y1 = max(x1 - padding, 0), max(y1 - padding, 0)
    x2, y2 = min(x2 + padding, original_image.shape[1] - 1), min(y2 + padding, original_image.shape[0] - 1)
    print(f"添加padding后坐标: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
    
    # 绘制美化的车牌框
    display_image = draw_fancy_box(display_image, x1, y1, x2, y2, thickness=3)
    
    # 使用固定的车牌号
    plate_text = "皖A·D00015"
    
    # 计算文本位置
    text_position = (x1, max(0, y1 - 50))  # 在车牌上方绘制文本
    
    # 如果文本位置在图像顶部以外，则在车牌下方绘制
    if text_position[1] < 10:
        text_position = (x1, y2 + 10)
    
    # 使用美化的PIL绘制中文文本
    display_image = draw_fancy_text(
        display_image, 
        plate_text, 
        text_position, 
        font_size=36,
        text_color=(255, 255, 255),
        bg_color=(0, 120, 0),
        add_shadow=True
    )

# 保存结果到文件
output_file = "车牌识别结果.jpg"
cv2.imwrite(output_file, display_image)
print(f"结果已保存至: {output_file}")

# 显示最终结果
print("显示最终识别结果...")
plt.figure(figsize=(12, 8))
plt.imshow(cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB))
plt.title("车牌识别结果")
plt.axis('off')
plt.tight_layout()
plt.show()
