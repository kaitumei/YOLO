"""
验证码工具类
"""
import random
import string

class Captcha:
    """生成和验证验证码的工具类"""
    
    @staticmethod
    def generate_text(length=4):
        """生成随机验证码文本"""
        characters = string.digits + string.ascii_uppercase
        return ''.join(random.choice(characters) for _ in range(length))
    
    @staticmethod
    def generate_math():
        """生成数学计算验证码"""
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        operator = random.choice(['+', '-', '*'])
        
        if operator == '+':
            result = num1 + num2
        elif operator == '-':
            # 确保结果为正数
            if num1 < num2:
                num1, num2 = num2, num1
            result = num1 - num2
        else:  # 乘法
            # 使用较小的数字避免结果过大
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            result = num1 * num2
            
        question = f"{num1} {operator} {num2} = ?"
        return {'question': question, 'answer': str(result)} 