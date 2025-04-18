from flask import Blueprint

bp = Blueprint('monitor', __name__, url_prefix='/monitor')

from . import views 