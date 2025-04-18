from celery import Celery
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_caching import Cache
from flask_avatars import Avatars
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
mail = Mail()
cache = Cache()
avatars = Avatars()
socketio = SocketIO()
cors = CORS()
csrf = CSRFProtect()
