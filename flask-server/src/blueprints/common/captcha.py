import random
import string
from PIL import Image, ImageDraw, ImageFont
import io
import base64

class Captcha:
    """验证码生成类"""
    
    def __init__(self, width=120, height=40, length=4, font_size=30):
        self.width = width
        self.height = height
        self.length = length
        self.font_size = font_size
        self.code = self._generate_code()
        self.image = self._generate_image()
    
    def _generate_code(self):
        """生成随机验证码"""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(self.length))
    
    def _generate_image(self):
        """生成验证码图片"""
        # 创建空白图片
        image = Image.new('RGB', (self.width, self.height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        
        # 添加干扰线
        for i in range(5):
            x1 = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            x2 = random.randint(0, self.width)
            y2 = random.randint(0, self.height)
            draw.line([(x1, y1), (x2, y2)], fill=(0, 0, 0), width=1)
        
        # 添加干扰点
        for i in range(30):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            draw.point((x, y), fill=(0, 0, 0))
        
        # 添加验证码文字
        try:
            # 尝试加载系统字体
            font = ImageFont.truetype("arial.ttf", self.font_size)
        except IOError:
            # 如果找不到字体，使用默认字体
            font = ImageFont.load_default()
        
        # 计算文字位置
        text_width = draw.textlength(self.code, font=font)
        text_height = self.font_size
        x = (self.width - text_width) / 2
        y = (self.height - text_height) / 2
        
        # 绘制文字
        for i, char in enumerate(self.code):
            # 每个字符使用不同的颜色
            color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
            draw.text((x + i * (text_width / self.length), y), char, font=font, fill=color)
        
        return image
    
    def get_base64(self):
        """获取Base64编码的图片"""
        buffer = io.BytesIO()
        self.image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{img_str}"
    
    def verify(self, user_input):
        """验证用户输入是否正确"""
        return user_input.lower() == self.code.lower() 