import os

from flask import Flask


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.urandom(32)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
