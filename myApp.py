from flask import Flask
from dotenv import load_dotenv 
from datetime import timedelta

import logging
import os

load_dotenv()

app = Flask(__name__)
app.debug = os.environ.get("DEBUG", "False").lower() != "False"
app.logger.setLevel(logging.INFO)

app.secret_key = os.environ.get("SECRET_KEY")
app.permanent_session_lifetime = timedelta(days=31)


print(f"Database Url: {os.environ.get('DATABASE_URL')}")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL").replace("postgres://","postgresql://")

twilio_sid = os.environ.get("TWILIO_SID")
twilio_auth = os.environ.get("TWILIO_AUTH")
twilio_number = os.environ.get("TWILIO_NUMBER")

gpt_api_key = os.environ.get("GPT_API_KEY")
gpt_engine = os.environ.get("GPT_ENGINE")
