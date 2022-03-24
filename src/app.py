#!/usr/bin/env python
# encoding: utf-8
from __future__ import annotations
import json
import bson
from flask import Flask, request, jsonify, redirect, url_for
from flask_mongoengine import MongoEngine
from flask_cors import CORS, cross_origin
from flask_login import current_user, login_required, login_user, UserMixin
from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['MONGODB_SETTINGS'] = {
    'db': 'sample_database',
    'host': 'localhost',
    'port': 27017
}
app.config['SECRET_KEY'] = '1a2b9bdd22abaed4d12e236c78afcb9a393ec15f71bbf5dc987d54727823bcc0'
db = MongoEngine(app)
login = LoginManager(app)


def response_with_cors(response, origin):
    response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response


class User(UserMixin, db.Document):
    uid = db.ObjectIdField(default=bson.ObjectId, primary_key=True)
    email = db.StringField()
    password_hash = db.StringField()

    def to_json(self):
        return {
            "email": self.email}

    def get_id(self):
        return str(self.uid)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login.user_loader
def load_user(id):
    print("Loader id={}".format(id))
    return User.objects(uid=id).first()


# TODO: Used for debugging.
user = User.objects(email="maverick@gmail.com").first()
if not user:
    print("Creating new user")
    user = User(email="maverick@gmail.com")
    user.save()
else:
    user.set_password("foo1234!")
    user.save()


@app.route('/v1/login', methods=['POST'])
def login():
    print("A")
    if current_user.is_authenticated:
        print("B")
        return response_with_cors(jsonify(current_user.to_json()), request.environ.get('HTTP_ORIGIN', '*'))
    print("C")
    record = json.loads(request.data)
    email = record['email']
    if not email:
        print("D")
        return response_with_cors(jsonify({'error': 'email empty'}), request.environ.get('HTTP_ORIGIN', '*'))
    print("E")
    password = record['password']
    if not password:
        print("F")
        return response_with_cors(jsonify({'error': 'password empty'}), request.environ.get('HTTP_ORIGIN', '*'))
    print("G")
    user = User.objects(email=email).first()
    if user is None or not user.check_password(password):
        print("H")
        print("User doesn't exist or bad password")
        return redirect(url_for('login'))
    print("I")
    login_user(user)
    return response_with_cors(jsonify(user.to_json()), request.environ.get('HTTP_ORIGIN', '*'))


@app.route('/v1/list', methods=['GET'])
@login_required
def query_records():
    print("Successfully Authenticated!")
    return response_with_cors(jsonify({'msg': 'success'}), request.environ.get('HTTP_ORIGIN', '*'))


if __name__ == "__main__":
    app.run(debug=True)
