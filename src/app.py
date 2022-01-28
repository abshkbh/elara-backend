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
    time_stamp: db.StringField()
    content: db.StringField()

    def to_json(self):
        return {
            "time_stamp": self.time_stamp,
            "content": self.content}


class Annotations(db.EmbeddedDocument):
    annotations = db.EmbeddedDocumentListField(Annotation)

    def to_json(self):
        return {
            "annotations": self.annotations}


class User(db.Document):
    name = db.StringField()
    email = db.StringField()
    # Maps YT video id => [{"time_stamp": XX, "content": YY}, ...].
    annotations = db.MapField(db.EmbeddedDocumentField(Annotations))

    def to_json(self):
        return {"name": self.name,
                "email": self.email,
                "annotations": self.annotations}


user = User(name="Abhishek", email="youo@gmail.com")
user.save()
print("After Save")


@app.route('/v1/', methods=['GET'])
def query_records():
    name = request.args.get('name')
    user = User.objects(name=name).first()
    if not user:
        return jsonify({'error': 'data not found'})
    else:
        return jsonify(user.to_json())


@app.route('/v1/', methods=['PUT'])
def create_record():
    record = json.loads(request.data)
    user = User(name=record['name'],
                email=record['email'])
    user.save()
    return jsonify(user.to_json())


@app.route('/v1/', methods=['POST'])
def update_record():
    record = json.loads(request.data)
    user = User.objects(name=record['name']).first()
    if not user:
        return jsonify({'error': 'data not found'})
    else:
        user.update(email=record['email'])
    return jsonify(user.to_json())


@app.route('/v1/', methods=['DELETE'])
def delete_record():
    record = json.loads(request.data)
    user = User.objects(name=record['name']).first()
    if not user:
        return jsonify({'error': 'data not found'})
    else:
        user.delete()
    return jsonify(user.to_json())


if __name__ == "__main__":
    app.run(debug=True)
