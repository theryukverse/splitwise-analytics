import os

from dotenv import load_dotenv
from flask import Flask

from views import views

from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())
app.config["STATIC_URL_PATH"] = "/static"
app.register_blueprint(views, url_prefix="/")

if __name__ == "__main__":
    app.run(debug=True)
