from flask import Blueprint, request, jsonify, g
from src.utils.exts import cache

bp = Blueprint('common', __name__, url_prefix='/common')

@bp.route('/')
def index():
    return 'common index'
