import os

from dotenv import load_dotenv
from flask import Flask

from views import views

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())
app.config["STATIC_URL_PATH"] = "/static"
app.register_blueprint(views, url_prefix="/")

if __name__ == "__main__":
    app.run(debug=True)
