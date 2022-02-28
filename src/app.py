#!/usr/bin/env python
# encoding: utf-8
from __future__ import annotations
import json
from flask import Flask, request, jsonify
from flask_mongoengine import MongoEngine

app = Flask(__name__)
app.config['MONGODB_SETTINGS'] = {
    'db': 'your_database',
    'host': 'localhost',
    'port': 27017
}
db = MongoEngine()
db.init_app(app)


class Annotation(db.EmbeddedDocument):
    time_stamp = db.StringField()
    content = db.StringField()

    def to_json(self):
        return {
            "time_stamp": self.time_stamp,
            "content": self.content}


class User(db.Document):
    email = db.StringField()
    # Maps YT video id => [{"time_stamp": XX, "content": YY}, ...].
    annotations = db.MapField(db.EmbeddedDocumentListField(Annotation))

    def to_json(self):
        return {
            "email": self.email,
            "annotations": self.annotations}


user = User(email="maverick@gmail.com", annotations={})
user.save()
print("After Save")


@app.route('/v1/list/', methods=['GET'])
def query_records():
    print("In GET")
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'email empty'})
    user = User.objects(email=email).first()
    if not user:
        return jsonify({'error': 'data not found'})
    else:
        return jsonify(user.to_json())


@app.route('/v1/add/', methods=['PUT'])
def create_record():
    record = json.loads(request.data)
    email = record['email']
    # Id extracted from a Youtube URL.
    video_id = record["video_id"]
    time_stamp = record["ts"]
    content = record["content"]
    print("email {} video_id {} Ts {} Content {}".format(
        email, video_id, time_stamp, content))
    user = User.objects(email=email).first()
    if not user:
        return jsonify({'error': 'data not found'})

    # If the url has a "period" in it then mongo engine will complain while saving the object.
    # TODO: Same time stamps are added not updated.
    user.annotations.setdefault(video_id, []).append(Annotation(
        time_stamp=time_stamp, content=content))
    user.save()
    return jsonify(user.to_json())


@ app.route('/v1/', methods=['POST'])
def update_record():
    record = json.loads(request.data)
    user = User.objects(email=record['email']).first()
    if not user:
        return jsonify({'error': 'data not found'})
    else:
        user.update(email=record['email'])
    return jsonify(user.to_json())


@ app.route('/v1/', methods=['DELETE'])
def delete_record():
    record = json.loads(request.data)
    user = User.objects(email=record['email']).first()
    if not user:
        return jsonify({'error': 'data not found'})
    else:
        user.delete()
    return jsonify(user.to_json())


if __name__ == "__main__":
    app.run(debug=True)
