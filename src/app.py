#!/usr/bin/env python
# encoding: utf-8
from __future__ import annotations
import json
import bson
from flask import Flask, request, jsonify, redirect, url_for
from flask_mongoengine import MongoEngine
from flask_cors import CORS, cross_origin
from flask_login import current_user, login_user, UserMixin
from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)
app.config['MONGODB_SETTINGS'] = {
    'db': 'your_database',
    'host': 'localhost',
    'port': 27017
}
app.config['SECRET_KEY'] = '1a2b9bdd22abaed4d12e236c78afcb9a393ec15f71bbf5dc987d54727823bcc0'
db = MongoEngine(app)
login = LoginManager(app)


def response_with_cors(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


class Annotation(db.EmbeddedDocument):
    time_stamp = db.StringField()
    content = db.StringField()

    def to_json(self):
        return {
            "time_stamp": self.time_stamp,
            "content": self.content
        }


class User(UserMixin, db.Document):
    uid = db.ObjectIdField(default=bson.ObjectId, primary_key=True)
    email = db.StringField()
    password_hash = db.StringField()
    # Maps YT video id => [{"time_stamp": XX, "content": YY}, ...].
    annotations = db.MapField(db.EmbeddedDocumentListField(Annotation))
    # Maps YT video id to its title. E.g. "abcd34sq" => "Top 10 moments of 2022".
    video_id_title_map = db.MapField(db.StringField())

    def to_json(self):
        return {
            "email": self.email,
            "annotations": self.annotations}

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
    user = User(email="maverick@gmail.com",
                annotations={}, video_id_title_map={})
    user.save()
else:
    user.set_password("foo1234!")
    user.save()


@app.route('/v1/login', methods=['POST'])
def login():
    print("A")
    if current_user.is_authenticated:
        print("B")
        return response_with_cors(jsonify(current_user.to_json()))
    print("C")
    record = json.loads(request.data)
    email = record['email']
    if not email:
        print("D")
        return response_with_cors(jsonify({'error': 'email empty'}))
    print("E")
    password = record['password']
    if not password:
        print("F")
        return response_with_cors(jsonify({'error': 'password empty'}))
    print("G")
    user = User.objects(email=email).first()
    if user is None or not user.check_password(password):
        print("H")
        print("User doesn't exist or bad password")
        return redirect(url_for('login'))
    print("I")
    login_user(user)
    return response_with_cors(jsonify(user.to_json()))


@app.route('/v1/list', methods=['GET'])
def query_records():
    print("In GET")
    email = request.args.get('email')
    if not email:
        return response_with_cors(jsonify({'error': 'email empty'}))
    user = User.objects(email=email).first()
    if not user:
        return response_with_cors(jsonify({'error': 'data not found'}))
    else:
        return response_with_cors(jsonify(user_videos=user.video_id_title_map))


@app.route('/v1/annotations', methods=['GET'])
def query_annotations():
    print("In GET")
    email = request.args.get('email')
    if not email:
        return response_with_cors(jsonify({'error': 'email empty'}))
    video_id = request.args.get('video_id')
    if not video_id:
        return response_with_cors(jsonify({'error': 'video id empty'}))
    user = User.objects(email=email).first()
    if not user:
        return response_with_cors(jsonify({'error': 'data not found'}))
    else:
        return response_with_cors(jsonify(annotations=user.annotations[video_id]))


@app.route('/v1/add', methods=['PUT'])
def create_record():
    record = json.loads(request.data)
    email = record['email']
    if not email:
        return response_with_cors(jsonify({'error': 'email empty'}))
    # Id extracted from a Youtube URL.
    video_id = record["video_id"]
    time_stamp = record["ts"]
    content = record["content"]
    video_title = record["video_title"]
    print("email {} video_id {} Ts {} Content {} video_title {}".format(
        email, video_id, time_stamp, content, video_title))
    user = User.objects(email=email).first()
    if not user:
        return response_with_cors(jsonify({'error': 'data not found'}))

    # If the url has a "period" in it then mongo engine will complain while saving the object.
    # TODO: Same time stamps are added not updated.
    user.annotations.setdefault(video_id, []).append(Annotation(
        time_stamp=time_stamp, content=content))
    user.video_id_title_map[video_id] = video_title
    user.save()
    return response_with_cors(jsonify(user.to_json()))


if __name__ == "__main__":
    app.run(debug=True)
