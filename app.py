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
    'db': 'your_database',
    'host': 'mongodb+srv://elaraadmin:test0000@cluster0.kh4nl.mongodb.net/myFirstDatabase?retryWrites=true&w=majority'
}
app.config['SECRET_KEY'] = '1a2b9bdd22abaed4d12e236c78afcb9a393ec15f71bbf5dc987d54727823bcc0'
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
db = MongoEngine(app)
login = LoginManager(app)


def response_with_cors(response, request):
    response.headers.add('Access-Control-Allow-Origin',
                         request.environ.get('HTTP_ORIGIN', '*'))
    response.headers.add('Access-Control-Allow-Credentials', 'true')
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
    user.set_password("foo1234!")
    user.save()


@app.route('/v1/login', methods=['POST'])
def login():
    print("XXX: In Login 1")
    if current_user.is_authenticated:
        print("XXX: In Login 2")
        return response_with_cors(jsonify(current_user.to_json()), request)

    print("XXX: In Login 3")
    record = json.loads(request.data)
    email = record['email']
    if not email:
        print("XXX: In Login 4")
        return response_with_cors(jsonify({'error': 'email empty'}), request)

    print("XXX: In Login 5")
    password = record['password']
    if not password:
        print("XXX: In Login 6")
        return response_with_cors(jsonify({'error': 'password empty'}), request)

    print("XXX: In Login 7")
    user = User.objects(email=email).first()
    if user is None or not user.check_password(password):
        print("XXX: In Login 8")
        print("User doesn't exist or bad password")
        return redirect(url_for('login'))

    print("XXX: In Login 9")
    login_user(user)
    return response_with_cors(jsonify(user.to_json()), request)


@app.route('/v1/list', methods=['GET'])
@login_required
def query_records():
    print("XXX: In query_records")
    return response_with_cors(jsonify(user_videos=current_user.video_id_title_map), request)


@app.route('/v1/annotations', methods=['GET'])
@login_required
def query_annotations():
    video_id = request.args.get('video_id')
    if not video_id:
        return response_with_cors(jsonify({'error': 'video id empty'}))
    return response_with_cors(jsonify(annotations=current_user.annotations[video_id]), request)


@app.route('/v1/add', methods=['PUT'])
@login_required
def create_record():
    record = json.loads(request.data)
    # Id extracted from a Youtube URL.
    video_id = record["video_id"]
    time_stamp = record["ts"]
    content = record["content"]
    video_title = record["video_title"]
    print("video_id {} Ts {} Content {} video_title {}".format(
        video_id, time_stamp, content, video_title))

    # If the url has a "period" in it then mongo engine will complain while saving the object.
    # TODO: Same time stamps are added not updated.
    current_user.annotations.setdefault(video_id, []).append(Annotation(
        time_stamp=time_stamp, content=content))
    current_user.video_id_title_map[video_id] = video_title
    current_user.save()
    return response_with_cors(jsonify(current_user.to_json()), request)


if __name__ == "__main__":
    app.run(debug=True)
