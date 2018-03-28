from flask import Flask
from . import db
from passlib.apps import  custom_app_context
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, SignatureExpired, BadSignature
import json
import datetime, time


class User(db.Model):

    __tablename__ = 'user'

    id = db.Column(db.Integer,primary_key=True, autoincrement=True, nullable=False)
    username = db.Column(db.VARCHAR(32), nullable=False)
    password = db.Column(db.VARCHAR(128), nullable=False)
    build_list = db.Column(db.VARCHAR(40), nullable=True, default=None)
    is_active = db.Column(db.Boolean, default=False)
    role = db.Column(db.Integer, default=3)

    def hash_password(self, password):
        self.password = custom_app_context.encrypt(password)

    def verify_password(self, password):
        return custom_app_context.verify(password, self.password)

    def generate_auth_token(self, expiration=1200):
        s = Serializer('SECRET_KEY', expires_in=expiration)
        access_token = s.dumps({ 'id': self.id, 'role': self.role})
        return access_token

    @staticmethod
    def verify_auth_token(token):
        s = Serializer('SECRET_KEY')
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None
        except BadSignature:
            return None
        user = User.query.get(data['id'])
        return user

    def __repr__(self):
        return '<User %r>' % self.username

class Building(db.Model):
    __tablename__ = 'building'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    building_name = db.Column(db.VARCHAR(40), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    address = db.Column(db.VARCHAR(200), nullable=True,default=None)
    city = db.Column(db.VARCHAR(40), nullable=True,default=None)
    zip_code = db.Column(db.Integer, nullable=True,default=None)
    date_start = db.Column(db.TIMESTAMP, nullable=True,default=None)
    water_heater_brand = db.Column(db.VARCHAR(40), nullable=True,default=None)
    water_heater_capacity = db.Column(db.Float(32), nullable=True,default=None)
    water_heater_rated_efficiency = db.Column(db.Float(32), nullable=True,default=None)
    storage_capacity = db.Column(db.Float(32), nullable=True,default=None)

    def to_json(self):
        build = {
            'id':self.id,
            'buildingName':self.building_name,
            'isActive':self.is_active,
            'address':self.address,
            'city':self.city,
            'zipCode':self.zip_code,
            'dateStart':str(self.date_start),
            'waterHeaterBrand':self.water_heater_brand,
            'waterHeaterCapacity':self.water_heater_capacity,
            'waterHeaterRatedEfficiency':self.water_heater_rated_efficiency,
            'storageCapacity':self.storage_capacity
        }
        return build

    def __repr__(self):
        return '<Building %r>' % self.building_name

class OptInput(db.Model):
    __tablename__ = 'opt_input'
    build_id = db.Column(db.Integer, db.ForeignKey('building.id'), primary_key=True)
    time = db.Column(db.TIMESTAMP, primary_key=True)
    hot_water = db.Column(db.VARCHAR(1000))
    ele_price = db.Column(db.VARCHAR(1000))
    amb_temperature = db.Column(db.VARCHAR(1000))
    solar_energy_output = db.Column(db.VARCHAR(1000))
    demand_response_scaler = db.Column(db.VARCHAR(1000))
    input_v1 = db.Column(db.Float(32), nullable=False)
    input_v2 = db.Column(db.Float(32), nullable=False)
    type = db.Column(db.Float(32), nullable=False)

    def to_json(self):
        opt = {
            'buildId':self.build_id,
            'time':str(self.time),
            'hotWater':self.hot_water.split(','),
            'elePrice':self.ele_price.split(','),
            'ambTemperature':self.amb_temperature.split(','),
            'solarEnergyOutput':self.solar_energy_output.split(','),
            'demandResponseScaler':self.demand_response_scaler.split(','),
            'input1':self.input_v1,
            'input2':self.input_v2,
            'type':self.type
        }
        return opt

    def __repr__(self):
        return '<OptInput %r>' % self.build_id


class Operational(db.Model):
    __tablename__ = 'operational'
    build_id = db.Column(db.Integer, db.ForeignKey('building.id'), primary_key=True)
    data_id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(64))

    def __repr__(self):
        return '<Operational %r>' % self.build_id

class Data32(db.Model):
    __tablename__ = 'data32'
    build_id = db.Column(db.Integer, db.ForeignKey('building.id'), primary_key=True)
    data_id = db.Column(db.String(64), primary_key=True)
    time = db.Column(db.TIMESTAMP, primary_key=True)
    data = db.Column(db.Float(32), nullable=False)

    def __repr__(self):
        return '<OptInput %r>' % self.build_id

class DataBoolean(db.Model):
    __tablename__ = 'data_boolean'
    build_id = db.Column(db.Integer, db.ForeignKey('building.id'), primary_key=True)
    data_id = db.Column(db.String(64), primary_key=True)
    time = db.Column(db.TIMESTAMP, primary_key=True)
    data = db.Column(db.Boolean, nullable=False)

    def __repr__(self):
        return '<DataBoolean %r>' % self.build_id

class Picture(db.Model):
    __tablename__ = 'picture'
    build_id = db.Column(db.Integer, db.ForeignKey('building.id'), primary_key=True)
    time = db.Column(db.TIMESTAMP, primary_key=True)
    src = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return '<Picture %r>' % self.build_id


class Com(db.Model):
    __tablename__ = 'command'
    id = db.Column(db.Integer,primary_key=True, autoincrement=True, nullable=False)
    build_id = db.Column(db.Integer, db.ForeignKey('building.id'))
    time = db.Column(db.TIMESTAMP, nullable=False, default=datetime.datetime.now)
    type = db.Column(db.Integer,nullable=False)
    parameter_v1 = db.Column(db.Float,nullable=True)
    parameter_v2 = db.Column(db.Float, nullable=True)
    action_time = db.Column(db.TIMESTAMP, nullable=True)
    status = db.Column(db.Integer,nullable=False, default=0)

    def __repr__(self):
        return '<Com %r>' % self.id