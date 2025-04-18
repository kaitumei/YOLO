from wtforms.validators import Email, Length, Regexp
from wtforms import FileField, BooleanField
from wtforms import StringField, ValidationError
from wtforms.validators import DataRequired, EqualTo
from wtforms.validators import Email, Length

from ..common.forms import BaseForm
from ..front.models import UserModel
from src.utils.exts import cache
from flask_wtf.file import FileAllowed
from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField

from flask import g
from wtforms import validators
import re

class RegisterForm(BaseForm):
    email = StringField(validators=[
        DataRequired(message="邮箱不能为空"),
        Email(message="请输入正确的邮箱格式！")
    ])
    captcha = StringField(validators=[
        DataRequired(message="验证码不能为空"),
        Length(min=4, max=4, message="请输入正确格式的验证码！")
    ])
    username = StringField(validators=[
        DataRequired(message="用户名不能为空"),
        Length(min=2, max=20, message="用户名长度必须在2-20个字符之间")
    ])
    password = StringField(validators=[
        DataRequired(message="密码不能为空"),
        Length(min=6, max=20, message="密码长度必须在6-20个字符之间")
    ])
    password2 = StringField(validators=[
        DataRequired(message="请确认密码"),
        EqualTo("password", message="两次输入的密码不一致！")
    ])

    def validate_email(self, field):
        email = field.data
        user = UserModel.query.filter_by(email=email).first()
        if user:
            raise ValidationError(message="邮箱已被注册！")

    def validate_captcha(self, field):
        captcha = field.data
        email = self.email.data
        cache_captcha = cache.get(email)
        if not cache_captcha or cache_captcha != captcha:
            raise ValidationError(message="验证码错误！！")
            
    def validate_username(self, field):
        username = field.data
        user = UserModel.query.filter_by(username=username).first()
        if user:
            raise ValidationError(message="用户名已被使用！")
        
        # 检查用户名是否包含特殊字符
        if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', username):
            raise ValidationError(message="用户名只能包含字母、数字、下划线和中文字符")

class LoginForm(BaseForm):
    account = StringField(validators=[
        DataRequired(message="账号不能为空"),
        Length(min=2, max=50, message="账号长度必须在2-50个字符之间")
    ])
    password = StringField(validators=[
        DataRequired(message="密码不能为空"),
        Length(min=6, max=20, message="密码长度必须在6-20个字符之间")
    ])
    remember = BooleanField()
    
    def validate_account(self, field):
        # 此处不验证格式，允许用户使用用户名或邮箱登录
        pass

class EditProfileForm(BaseForm):
    username = StringField(validators=[Length(min=2, max=50, message="请输入正确长度的用户名！")])
    avatar = FileField(validators=[FileAllowed(['jpg', 'jpeg', 'png'], message="仅支持图片格式")])
    signature = StringField()

    def validate_signature(self, field):
        signature = field.data
        if signature and len(signature) > 100:
            raise ValidationError(message="个性签名不能超过100个字符！")

from flask_wtf import FlaskForm  # 正确导入 FlaskForm
from wtforms import PasswordField, validators
from wtforms.validators import ValidationError

class ChangePasswordForm(FlaskForm):  # ✅ 继承 FlaskForm
    old_password = PasswordField("旧密码", validators=[validators.InputRequired("旧密码不能为空")])
    new_password = PasswordField("新密码", validators=[
        validators.InputRequired("新密码不能为空"),
        validators.Length(min=6, message="密码至少6位")
    ])
    confirm_password = PasswordField("确认密码", validators=[
        validators.InputRequired("请确认密码"),
        validators.EqualTo("new_password", message="两次密码不一致")
    ])

    def validate_old_password(self, field):
        if not g.user.check_password(field.data):
            raise ValidationError("旧密码错误")


class ChangeEmailForm(FlaskForm):
    old_email = StringField("原邮箱", validators=[
        DataRequired("原邮箱不能为空"),
        Email("邮箱格式无效")
    ])

    new_email = StringField("新邮箱", validators=[
        DataRequired("新邮箱不能为空"),
        Email("新邮箱格式无效"),
        EqualTo("confirm_email", message="两次输入的邮箱不一致")
    ])

    confirm_email = StringField("确认新邮箱")

    password = PasswordField("密码", validators=[
        DataRequired("需要密码验证身份")
    ])

    def validate_old_email(self, field):
        if field.data != g.user.email:
            raise ValidationError("原邮箱不匹配")

    def validate_new_email(self, field):
        if UserModel.query.filter_by(email=field.data).first():
            raise ValidationError("该邮箱已被注册")


class ForgotPasswordForm(FlaskForm):
    email = StringField('注册邮箱', validators=[
        DataRequired("邮箱不能为空"),
        Email("邮箱格式不正确")
    ])

class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('新密码', validators=[
        DataRequired("新密码不能为空"),
        validators.Length(min=6, message="密码至少6位")
        # Regexp(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{6,}$',
        #        message="密码需至少8位，包含字母和数字")
    ])
    confirm_password = PasswordField('确认密码', validators=[
        DataRequired("请确认密码"),
        EqualTo('new_password', message="两次密码不一致")
    ])

class PhoneRegisterForm(BaseForm):
    phone = StringField(validators=[
        DataRequired(message="手机号不能为空"),
        Regexp(r'^1[3-9]\d{9}$', message="请输入正确的手机号格式！")
    ])
    captcha = StringField(validators=[
        DataRequired(message="验证码不能为空"),
        Length(min=4, max=4, message="请输入正确格式的验证码！")
    ])
    username = StringField(validators=[
        DataRequired(message="用户名不能为空"),
        Length(min=2, max=20, message="用户名长度必须在2-20个字符之间")
    ])
    password = StringField(validators=[
        DataRequired(message="密码不能为空"),
        Length(min=6, max=20, message="密码长度必须在6-20个字符之间")
    ])
    password2 = StringField(validators=[
        DataRequired(message="请确认密码"),
        EqualTo("password", message="两次输入的密码不一致！")
    ])

    def validate_phone(self, field):
        phone = field.data
        user = UserModel.query.filter_by(phone=phone).first()
        if user:
            raise ValidationError(message="手机号已被注册！")

    def validate_captcha(self, field):
        captcha = field.data
        phone = self.phone.data
        cache_captcha = cache.get(f'sms_{phone}')
        if not cache_captcha:
            raise ValidationError(message="验证码已过期，请重新获取！")
        if cache_captcha != captcha:
            raise ValidationError(message="验证码错误！")
            
    def validate_username(self, field):
        username = field.data
        user = UserModel.query.filter_by(username=username).first()
        if user:
            raise ValidationError(message="用户名已被使用！")
        
        # 检查用户名是否包含特殊字符
        if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', username):
            raise ValidationError(message="用户名只能包含字母、数字、下划线和中文字符")