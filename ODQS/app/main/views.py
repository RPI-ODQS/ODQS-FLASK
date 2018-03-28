from app import auth, mqtt_ws
from flask import render_template, jsonify, request, g, make_response, send_from_directory, url_for
from . import main
from .. import db
from ..models import *
import json
import string
import datetime, time
import tablib
import os
import threading
from werkzeug.utils import secure_filename
from flask_mqtt import Mqtt

import logging

@main.route('/')
def hello():
    print()
    return '<h1>hello world<h1>'

@auth.verify_password
def verify_password(username_or_token,password):
    print(username_or_token, password)
    if request.path == '/login':
        user = User.query.filter_by(username = username_or_token).first()
        if not user or not user.verify_password(password):
            print("false")
            return False
    else:
        user = User.verify_auth_token(username_or_token)
        if not user:
            print("false")
            return False
    g.user = user
    return True

@auth.error_handler
def unauthorized():
    res = make_response(jsonify({'error': 'Unauthorized access'}), 401)
    res.headers['WWW-Authenticate'] = ''
    return res

@main.route('/login', methods=['POST','GET'])
@auth.login_required
def index():
    if request.method == 'POST' or request.method == 'GET':
        data = request.get_data()
        #
        # data = data.decode("utf-8")
        # j_data = json.loads(data)
        # return jsonify(j_data)
        print(request.headers)
        token = g.user.generate_auth_token()
        token = token.decode("utf-8")
        return jsonify(token=token, role=g.user.role)


@main.route('/buildings', methods=['GET', 'PUT', 'POST'])
@auth.login_required
def get_building():
    if request.method == 'GET':
        print(request.headers)
        user_id = g.user.id
        user = User.query.filter_by(id = user_id).first()
        if not user:
            return None
        building_list = user.build_list
        if building_list is not None and building_list != '':
            print(building_list)
            building_list = building_list.split(',')
        res = []

        if user.role != 3:
            build_all = Building.query.all()
            for v in build_all:
                res.append({'id': v.id, 'name': v.building_name})
        else:
            for v in building_list:
                temp = Building.query.filter_by(id = v).first()
                if not temp:
                    continue
                res.append({'id':v, 'name':temp.building_name})
        return jsonify(buildings=res)

    if request.method == 'PUT':
        data = request.get_data()
        data = data.decode("utf-8")
        data = json.loads(data)
        print(data)
        name = data['buildingName'] if 'buildingName' in data else None
        id = data['buildingId'] if 'buildingId' in data else None
        if not name:
            return jsonify(status='faild')
        if id:
            build = Building.query.filter_by(id = id).first()
            if not build:
                return jsonify(status='faild, building is not exist')
        else:
            build = Building(building_name = name)
            build.id = 0

        build.building_name = name
        build.is_active = data['isActive'] if 'is_active' in data else None
        build.address = data['address'] if 'address' in data else None
        build.city = data['city'] if 'city' in data else None
        build.zipCode = data['zipCode'] if 'zipCode' in data else None
        build.dateStart = data['dateStart'] if 'dateStart' in data else None
        build.waterHeaterBrand = data['waterHeaterBrand'] if 'waterHeaterBrand' in data else None
        build.waterHeaterCapacity = data['waterHeaterCapacity'] if 'waterHeaterCapacity' in data else None
        build.waterHeaterRatedEfficiency = data['waterHeaterRatedEfficiency'] if 'waterHeaterRatedEfficiency' in data else None
        build.storageCapacity = data['storageCapacity'] if 'storageCapacity' in data else None
        db.session.add(build)
        db.session.flush()
        id = build.id
        db.session.commit()
        return jsonify(status='success', id=id)



@main.route('/msc',methods=['GET'])
@auth.login_required
def msc():
    if request.method == 'GET':
        data = request.args
        print(data)
        building_id = data['id']
        if building_id is None:
            return None
        build = Building.query.filter_by(id = building_id).first()
        if not build:
            return None
        res = build.to_json()
        return jsonify(res)

@main.route('/opi', methods=['GET'])
@auth.login_required
def opi():
    if request.method == 'GET':
        data = request.args
        building_id = data['id']
        if building_id is None:
            print('no building')
            return None
        build = OptInput.query.filter_by(build_id = building_id).first()
        if not build:
            return jsonify(status="not found")
        res = build.to_json()
        print(res)
        return jsonify(res)



@main.route('/update/opi',methods=['POST'])
@auth.login_required
def opi_update():
    if request.method == 'POST':
        data = request.get_data()
        data = data.decode("utf-8")
        data = json.loads(data)
        print(data)
        add = 0
        building_id = data['buildingId']
        print(data['hotWater'])
        print(type(data['hotWater']))
        hotWater = ','.join(data['hotWater'])
        ambientTemperature = ','.join(data['ambientTemperature'])
        electricityPrice = ','.join(data['electricityPrice'])
        solarEnergyOutput = ','.join(data['solarEnergyOutput'])
        demandResponse = ','.join(data['demandResponse'])
        inputVar1 = data['inputVar1']
        inputVar2 = data['inputVar2']
        input_type = data['type']
        opi_time = data['time']

        opi = OptInput.query.filter_by(build_id = building_id).first()
        if not opi:
            add = 1
            opi = OptInput(build_id = building_id)
        opi.hot_water = hotWater
        opi.ele_price = electricityPrice
        opi.amb_temperature = ambientTemperature
        opi.solar_energy_output = solarEnergyOutput
        opi.demand_response_scaler = demandResponse
        opi.input_v1 = inputVar1
        opi.input_v2 = inputVar2
        opi.type = input_type
        opi.time = opi_time
        if add == 1:
            db.session.add(opi)
        db.session.commit()

        message = opi.to_json()
        print(str(message['time']))
        message = json.dumps(message)
        print(type(message))
        mqtt_ws.publish('/opi/'+str(building_id), message)

        return jsonify(status='success')

#Flow Temperature, Pressure, Current, Relay state, Control
@main.route('/sos/header', methods=['GET'])
@auth.login_required
def sos_header():
    data = request.args
    print(data['buildingId'])
    building_id = data['buildingId']
    if building_id is None:
        return None
    control = Operational.query.filter_by(build_id = building_id).all()
    res = {'temperature':{}, 'flow':{}, 'pressure':{}, 'current':{}, 'switch':{}, 'output':{}}
    for each in control:
        if each.data_id.startswith('Temperature'):
            res['temperature'][each.data_id] = each.name
        elif each.data_id.startswith('Flow'):
            res['flow'][each.data_id] = each.name
        elif each.data_id.startswith('Pressure'):
            res['pressure'][each.data_id] = each.name
        elif each.data_id.startswith('Current'):
            res['current'][each.data_id] = each.name
        elif each.data_id.startswith('Switch'):
            res['switch'][each.data_id] = each.name
        elif each.data_id.startswith('Output'):
            res['output'][each.data_id] = each.name
    return jsonify(res)


@main.route('/sos/data', methods=['GET','POST'])
@auth.login_required
def sos_data():
    data = request.get_data()
    data = data.decode("utf-8")
    data = json.loads(data)
    res = {'temperature': {}, 'flow': {}, 'pressure': {}, 'current': {}, 'switch': {}, 'output': {}}

    a = datetime.datetime.strptime(data['timeFrom'], '%Y-%m-%d %H')
    b = datetime.datetime.strptime(data['timeTo'], '%Y-%m-%d %H')
    diff = (b-a).seconds/24

    sensorname = Operational.query.filter_by(build_id = data['buildingId']).all()
    for each in sensorname:
        if each.data_id.startswith('Temperature'):
            res['temperature'][each.data_id] = {}
            res['temperature'][each.data_id]['sensorName'] = each.name
            res['temperature'][each.data_id]['data'] = [0]*24
        elif each.data_id.startswith('Flow'):
            res['flow'][each.data_id] = {}
            res['flow'][each.data_id]['sensorName'] = each.name
            res['flow'][each.data_id]['data'] = [0] * 24
        elif each.data_id.startswith('Pressure'):
            res['pressure'][each.data_id] = {}
            res['pressure'][each.data_id]['sensorName'] = each.name
            res['pressure'][each.data_id]['data'] = [0] * 24
        elif each.data_id.startswith('Current'):
            res['current'][each.data_id] = {}
            res['current'][each.data_id]['sensorName'] = each.name
            res['current'][each.data_id]['data'] = [0] * 24
        # elif each.data_id.startswith('Switch'):
        #     res['switch'][each.data_id] = {}
        #     res['switch'][each.data_id]['sensorName'] = each.name
        #     res['switch'][each.data_id]['data'] = [0] * 24
        elif each.data_id.startswith('Output'):
            res['output'][each.data_id] = {}
            res['output'][each.data_id]['sensorName'] = each.name
            res['output'][each.data_id]['data'] = [0] * 24
    print(res)

    if data['timeTo'] == '' or data['timeTo'] is None:
        res32 = Data32.query.filter(Data32.build_id == data['buildingId'], Data32.time >= a).all()
    else:
        res32 = Data32.query.filter(Data32.build_id == data['buildingId'], Data32.time >= a, Data32.time < b).all()

    for each in res32:
        i = (each.time - a).seconds / diff
        i = int(i)
        if each.data_id.startswith('Temperature'):
            res['temperature'][each.data_id]['data'][i] += each.data
        elif each.data_id.startswith('Flow'):
            res['flow'][each.data_id]['data'][i] += each.data
        elif each.data_id.startswith('Pressure'):
            res['pressure'][each.data_id]['data'][i] += each.data
        elif each.data_id.startswith('Current'):
            res['current'][each.data_id]['data'][i] += each.data
        # elif each.data_id.startswith('Switch'):
        #     res['switch'][each.data_id]['data'][i] += each.data
        elif each.data_id.startswith('Output'):
            res['output'][each.data_id]['data'][i] += each.data

    for each in res:
        print(each)
        for sensor in res[each]:
            print(sensor)
            for index in range(len(res[each][sensor]['data'])):
                res[each][sensor]['data'][index] = res[each][sensor]['data'][index]*10/diff
    res['step'] = diff
    return jsonify(res)


@main.route('/sos/csv/<filename>', methods=['GET'])
def download(filename):
    dir = os.path.dirname(os.path.dirname(__file__))
    dir = os.path.join(dir, 'templates')
    return send_from_directory(dir, filename)



@main.route('/sos/csv', methods=['GET'])
@auth.login_required
def sos_download():
    data = request.args
    print(data)

    # a = datetime.datetime.strptime(data['timeFrom'], '%Y-%m-%d %H')
    # b = datetime.datetime.strptime(data['timeTo'], '%Y-%m-%d %H')

    if data['timeTo'] == '' or data['timeTo'] is None:
        res32 = Data32.query.filter(Data32.build_id == data['buildingId'], Data32.time >= data['timeFrom']).all()
    else:
        res32 = Data32.query.filter(Data32.build_id == data['buildingId'], Data32.time >= data['timeFrom'], Data32.time <= ['timeTo']).all()

    headers = ['time']
    sensor = json.loads(data['sensorsIds'])
    for k in sensor:
        headers = headers + sensor[k]
    temp = {}
    data = []
    for each in res32:
        time = each.time.strftime('%Y-%m-%d %H:%M:%S')
        if time not in temp.keys():
            temp[time] = {}
        temp[time][each.data_id] = each.data
    print(temp)
    for k in temp.keys():
        temp_date = []
        for i in headers:
            if i == 'time':
                temp_date.append(k)
                continue
            if i in temp[k].keys():
                temp_date.append(temp[k][i])
            else:
                temp_date.append(None)

        # del(temp[k])
        temp_date = tuple(temp_date)
        data.append(temp_date)
    data.sort()
    headers = tuple(headers)
    print(headers)
    print(data)
    dir = os.path.dirname(os.path.dirname(__file__))
    data = tablib.Dataset(*data, headers=headers)
    dir = os.path.join(dir, 'templates')
    filename = 'file.csv'
    f = open(dir+'/'+filename, 'w')
    f.write(data.csv)
    f.close()
    return jsonify(url='/sos/csv/'+filename)



@main.route('/sos/update', methods=['POST'])
@auth.login_required
def sos_update():
    if request.method == 'POST':
        basedir = os.path.dirname(os.path.dirname(__file__))
        file_dir = os.path.join(basedir, 'upload')
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)
        f = request.files['myfile']  # 从表单的file字段获取文件，myfile为该表单的name值
        if f :  # 判断是否是允许上传的文件类型
            fname = secure_filename(f.filename)

            ext = fname.rsplit('.', 1)[1]  # 获取文件后缀
            unix_time = int(time.time())
            new_filename = str(unix_time) + '.' + ext  # 修改了上传的文件名
            f.save(os.path.join(file_dir, new_filename))

            return jsonify(status='success')
        else:
            return jsonify(status='false')


@main.route('/picture/<building_id>/<filename>', methods=['GET'])
def download_picture(building_id, filename):
    dir = '/home/image'
    dir = os.path.join(dir, building_id)
    return send_from_directory(dir, filename)


@main.route('/picture', methods=['GET'])
@auth.login_required
def get_picture():
    data = request.args
    build_id = data['buildingId'] if 'buildingId' in data else None
    if build_id == None:
        return jsonify(status='fail')
    if data['timeTo'] == '' or data['timeTo'] is None:
        picture = Picture.query.filter(Picture.build_id == build_id, Picture.time>= data['timeFrom']).all()
    else:
        picture = Picture.query.filter(Picture.build_id == build_id, Picture.time >= data['timeFrom'], Data32.time <= ['timeTo']).all()

    url = []
    for each in picture:
        temp = '/picture'
        temp += '/'+build_id+'/'+str(each.time)+'.jpg'
        url.append(temp)

    return url




@main.route('/user', methods = ['PUT', 'DELETE', 'GET'])
@auth.login_required
def user_manage():
    user_role = g.user.role
    print(user_role)
    #权限不足
    if user_role == '3':
        return jsonify(status='1')

    if request.method == 'PUT':
        data = request.get_data()
        data = data.decode("utf-8")
        j_data = json.loads(data)
        print(j_data)
        username = j_data['username']
        password = j_data['password']
        building = j_data['buildingList']
        role = j_data['role'] if 'role' in data else 3
        if username is None or password is None:
            return jsonify(status = '1', str = 'username or password is NULL')
        if User.query.filter_by(username = username).first() is not None:
            return jsonify(status='1', str='the user has already existed ')
        user = User(username = username)
        user.hash_password(password)
        print(type(building))
        print(building)
        if building:
            user.build_list = str(building)[1:-1]
        else:
            user.build_list = None
        user.role = role
        db.session.add(user)
        db.session.commit()
        return jsonify(status='0')

    #仅限管理员
    if request.method == 'GET':
        data = request.args
        print(data)
        conditions = data['conditions']
        print(conditions)
        print(type(conditions))
        res = []
        if conditions is None or conditions == '':
            user = User.query.filter(User.role > user_role).all()
            if not user:
                return jsonify(user=res)
            for v in user:
                temp = v.build_list
                if temp != None:
                    temp = temp.split(',')
                res.append({'userId': v.id, 'userName': v.username, 'role': v.role, 'buildingList': temp})
        else:
            id = -1
            if conditions.isdigit():
                user = User.query.filter(User.id == conditions).first()
                if user:
                    res.append({'userId': user.id, 'userName': user.username, 'role': user.role,
                                'buildingList': user.build_list})
                    id = user.id
            user = User.query.filter(User.username.match(conditions)).all()
            for v in user:
                if v.id == id:
                    continue
                temp = v.build_list
                if temp != None:
                    temp = temp.split(',')
                res.append({'userId': v.id, 'userName': v.username, 'role': v.role, 'buildingList': temp})
        return jsonify(users=res)

    if request.method == 'DELETE':
        data = request.args
        id = data['userId']
        n_role = g.user.role
        if n_role >= int(id):
            return jsonify(status='fail')

        db.session.query(User).filter(User.id == id).delete(synchronize_session=False)
        db.session.commit()
        return jsonify(status='delete success')

@main.route('/update/user',methods=['POST'])
@auth.login_required
def update_user_info():
    n_user_id = g.user.id
    n_user = User.query.filter_by(id = n_user_id).first()

    data = request.get_data()
    data = data.decode("utf-8")
    data = json.loads(data)
    print(data)
    user_id = data['userId']
    username = data['newUsername']
    password = data['newPassword']
    build_list = data['newBuildingList']
    role = data['role']

    if username == '' and password == '':
        return jsonify(status='fail!')

    if n_user_id != user_id:
        u_user = User.query.filter_by(id=user_id).first()
        if n_user.role >= u_user.role:
            return jsonify(status='fail!')
        u_user.username = username
        u_user.id = user_id
        if password != "":
            u_user.hash_password(password)

        if build_list:
            u_user.build_list = str(build_list)[1,-1]
        if n_user.role == 1:
            if role == 1:
                role = 3
            u_user.role = role
            print (role)
        db.session.commit()

    else:
        n_user.username = username
        if password != "":
            n_user.hash_password(password)

        if build_list:
            n_user.build_list = str(build_list)[1, -1]
        db.session.commit()
    return jsonify(status='success')


@main.route('/data',methods = ['POST','GET'])
def data():

    data = request.get_data()
    data = data.decode("utf-8")
    data = json.loads(data)
    print(data)
    # a = datetime.datetime.strptime('2017-10-10 02', '%Y-%m-%d %H')
    # for i in range(1, 3601):
    #     a = a+datetime.timedelta(seconds=10)
    #     data = a.strftime('%Y-%m-%d %H:%M:%S')
    #     data32 = Data32(build_id = 1)
    #     data32.time = data
    #     data32.data_id = 'Temperature 1'
    #     data32.data = 23.33
    #     db.session.add(data32)
    # db.session.commit()
    return jsonify(status='Success')

@main.route('/command', methods=['POST', 'GET'])
@auth.login_required
def command():
    if request.method == 'POST':
        data = request.get_data()
        data = data.decode("utf-8")
        print(data)
        data = json.loads(data)

        build_id = data['buildingId'] if 'buildingId' in data else None
        type = data['type'] if 'type' in data else None
        par_v1 = data['parameterVar1'] if 'parameterVar1' in data else None
        par_v2 = data['parameterVar2'] if 'parameterVar2' in data else None
        com_time = data['time']
        com = Com(build_id = build_id)
        pub_com = {}
        if type != None:
            com.type = type
            pub_com['type'] = type
        else:
            return jsonify(status='error')

        if par_v1 != None:
            com.parameter_v1 = par_v1

        if par_v1 != None:
            com.parameter_v2 = par_v2

        com.time = com_time

        db.session.add(com)
        db.session.commit()
        com = Com.query.filter_by(build_id = build_id, time = com_time).first()
        pub_com['parameterVar1'] = par_v1
        pub_com['parameterVar2'] = par_v2
        pub_com['time'] = com_time
        pub_com['id'] = com.id
        pub_com = json.dumps(pub_com)
        # pub_com = str.encode(pub_com)
        mqtt_ws.publish('/comReq/'+str(build_id), pub_com)
        print("xxxxxx")

        # topic = '/comRes/' + build_id
        # mqtt_ws.subscribe(topic)
        # for n in range(1, 10):
        #     time.sleep(n)

        return jsonify(status='success')
    if request.method == 'GET':
        data = request.args
        print(data)
        build_id = data['buildingId']
        com = Com.query.filter(Com.build_id == build_id).order_by(Com.time).all()
        command = []
        if com:
            for each in com:
                temp = {}
                temp['buildingId'] = each.build_id
                temp['commandId'] = each.id
                temp['type'] = each.type
                temp['parameterVar1'] = each.parameter_v1
                temp['parameterVar2'] = each.parameter_v2
                temp['time'] = str(each.time)
                if each.action_time:
                    temp['actiomTime'] = None
                else:
                    print(str(each.action_time))
                    temp['actiomTime'] = str(each.action_time)
                temp['status'] =each.status
                command.append(temp)

        return jsonify(res=command)






