from wtforms import Form, StringField, validators, HiddenField
from wtforms.validators import Length, Regexp, InputRequired

class BaseForm(Form):
    @property
    def messages(self):
        message_list = []
        if self.errors:
            for errors in self.errors.values():
                message_list.extend(errors)
        return message_list

class CSRFTokenForm(BaseForm):
    csrf_token = HiddenField(validators=[InputRequired(message="CSRF令牌缺失")])
    
    def validate_csrf_token(self, field):
        from flask import session, abort
        token = session.get('csrf_token')
        if not token or token != field.data:
            abort(403)
