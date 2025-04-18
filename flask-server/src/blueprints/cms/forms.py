from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms import IntegerField
from wtforms import SelectField
from wtforms import BooleanField
from wtforms import TextAreaField
from wtforms import DateTimeField
from wtforms.validators import DataRequired
from wtforms.validators import Length
from wtforms.validators import Email
from wtforms.validators import InputRequired
from wtforms.validators import Optional
from wtforms.validators import URL
from ..common.forms import BaseForm


class AddBoardForm(BaseForm):
    name = StringField(validators=[Length(min=2, max=50, message="请输入正确长度的板块名称！")])
    desc = StringField(validators=[Length(max=200, message="请输入正确长度的板块描述！")])

class EditBoardForm(BaseForm):
    name = StringField(validators=[Length(min=2, max=50, message="请输入正确长度的板块名称！")])
    desc = StringField(validators=[Length(max=200, message="请输入正确长度的板块描述！")])

class AddContentForm(BaseForm):
    title = StringField(validators=[Length(min=2, max=50, message="请输入正确长度的内容标题！")])
    content = StringField(validators=[Length(max=200, message="请输入正确长度的内容！")])
    board_id = IntegerField(validators=[InputRequired(message="请选择板块！")])

class EditContentForm(BaseForm):
    title = StringField(validators=[Length(min=2, max=50, message="请输入正确长度的内容标题！")])
    content = StringField(validators=[Length(max=200, message="请输入正确长度的内容！")])
    board_id = IntegerField(validators=[InputRequired(message="请选择板块！")])

class AddLogForm(BaseForm):
    title = StringField(validators=[Length(min=2, max=50, message="请输入正确长度的日志标题！")])
    content = StringField(validators=[Length(max=200, message="请输入正确长度的日志内容！")])

class EditLogForm(BaseForm):
    title = StringField(validators=[Length(min=2, max=50, message="请输入正确长度的日志标题！")])
    content = StringField(validators=[Length(max=200, message="请输入正确长度的日志内容！")])


class AddStaffForm(BaseForm):
    email = StringField(validators=[Email(message="请输入正确的邮箱格式！")])
    role = IntegerField(validators=[InputRequired(message="请选择角色！")])

class EditStaffForm(BaseForm):
    username = StringField('用户名', validators=[
        DataRequired(message="用户名不能为空"),
        Length(2, 20, message="用户名长度2-20个字符")
    ])
    email = StringField('邮箱', validators=[
        DataRequired(message="邮箱不能为空"),
        Email(message="无效的邮箱格式"),
        Length(max=50, message="邮箱最长50个字符")
    ])
    role = SelectField('角色', coerce=int, validators=[
        DataRequired(message="必须选择角色")
    ])
    is_staff = BooleanField('系统职员')

class VehicleAppointmentApprovalForm(BaseForm):
    status = SelectField(
        "审批状态", 
        choices=[
            ('已通过', '通过'), 
            ('已拒绝', '拒绝')
        ],
        validators=[DataRequired(message="请选择审批状态")]
    )
    comment = StringField("备注", validators=[Optional()])

class BannerForm(BaseForm):
    title = StringField('标题', validators=[
        Length(max=100, message="标题最长100个字符")
    ])
    image_url = StringField('图片URL', validators=[
        DataRequired(message="图片URL不能为空"),
        Length(max=255, message="URL最长255个字符")
    ])
    link_url = StringField('链接URL', validators=[
        Optional(),
        Length(max=255, message="URL最长255个字符")
    ])
    sort_order = IntegerField('排序顺序', validators=[
        Optional()
    ])
    status = SelectField('状态', choices=[
        (1, '启用'),
        (0, '禁用')
    ], coerce=int)

class NoticeForm(BaseForm):
    title = StringField('标题', validators=[
        DataRequired(message="标题不能为空"),
        Length(max=100, message="标题最长100个字符")
    ])
    content = TextAreaField('内容', validators=[
        Optional()
    ])
    publish_time = DateTimeField('发布时间', format='%Y-%m-%dT%H:%M', validators=[
        DataRequired(message="发布时间不能为空")
    ])
    end_time = DateTimeField('结束时间', format='%Y-%m-%dT%H:%M', validators=[
        Optional()
    ])
    is_important = SelectField('重要性', choices=[
        (1, '重要'),
        (0, '普通')
    ], coerce=int)
    status = SelectField('状态', choices=[
        (1, '启用'),
        (0, '禁用')
    ], coerce=int)