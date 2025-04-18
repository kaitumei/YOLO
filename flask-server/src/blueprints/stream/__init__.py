from flask import Blueprint

bp = Blueprint('stream', __name__, url_prefix='/stream')

from . import views
