from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config
from flask_moment import Moment
from flask_httpauth import HTTPBasicAuth

import pymysql
pymysql.install_as_MySQLdb()
from flask_cors import *

from flask_mqtt import Mqtt

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_1, QOS_2


db = SQLAlchemy()
moment = Moment()
auth = HTTPBasicAuth()
mqtt_ws = Mqtt()

def create_app(config_name):
    app = Flask(__name__)
    CORS(app, supports_credentials=True)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    moment.init_app(app)
    db.init_app(app)

    app.config['MQTT_BROKER_URL'] = '127.0.0.1'
    app.config['MQTT_BROKER_PORT'] = 1883
    app.config['MQTT_USERNAME'] = ''
    app.config['MQTT_PASSWORD'] = ''
    app.config['MQTT_KEEPALIVE'] = 60
    app.config['MQTT_TLS_ENABLED'] = False
    app.config['MQTT_LAST_WILL_TOPIC'] = '/test'
    app.config['MQTT_LAST_WILL_MESSAGE'] = 'bye'
    app.config['MQTT_LAST_WILL_QOS'] = 2
    mqtt_ws.init_app(app)

    with app.app_context():
        db.create_all()

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
