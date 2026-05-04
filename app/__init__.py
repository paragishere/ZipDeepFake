import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask
from dotenv import load_dotenv

from flask_mail import Mail
from .db import init_db
from .utils import log_event

# 🔥 GLOBAL mail object (IMPORTANT)
mail = Mail()

# 🔥 load env
load_dotenv()


def create_app():
    app = Flask(__name__)

    # 🔐 BASIC CONFIG
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
    app.config['UPLOAD_FOLDER'] = 'uploads'

    # 🔥 MAIL CONFIG
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv("MAIL_EMAIL")
    app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

    # 🔥 INIT MAIL
    mail.init_app(app)

    # 🔥 DB INIT
    init_db()

    # 🔥 AUTO LOGGING
    @app.before_request
    def track_all_requests():
        try:
            log_event("VISIT")
        except:
            pass

    # 🔥 GOOGLE AUTH
    from flask_dance.contrib.google import make_google_blueprint

    google_bp = make_google_blueprint(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        redirect_url="/google_login",
        scope=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]
    )

    app.register_blueprint(google_bp, url_prefix="/login")

    # 🔥 ROUTES
    from .routes import main
    app.register_blueprint(main)

    return app