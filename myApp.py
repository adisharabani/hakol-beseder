from flask import Flask
from dotenv import load_dotenv 

import logging
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
app.debug = os.environ.get("DEBUG", "False").lower() != "False"

app.logger.setLevel(logging.INFO)

