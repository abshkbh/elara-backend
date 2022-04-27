#!/usr/bin/env python
# encoding: utf-8
from __future__ import annotations
import json
import bson
import requests
from flask import Flask, request, jsonify, make_response
from flask_mongoengine import MongoEngine
from flask_cors import CORS
from flask_login import current_user, login_required, login_user, logout_user, UserMixin
from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

# URL to hit to verify a Google OAuth token.
GOOGLE_OAUTH_TOKEN_VERIFICATION_URL = "https://oauth2.googleapis.com/tokeninfo"
# Query parameter to append to |GOOGLE_OAUTH_TOKEN_VERIFICATION_URL| to verify a Google OAuth token.
GOOGLE_OAUTH_TOKEN_VERIFICATION_URL_TOKEN_QUERY_PARAMETER = "id_token"

app = Flask(__name__)

# We will use sessions / cookies. This requires |support_credentials| to be True.
CORS(app, supports_credentials=True)

app.config["MONGODB_SETTINGS"] = {
    # TODO: Is this needed if we are using a cloud instance.
    "db": "your_database",
    # Mongo DB Instance in the cloud.
    "host": "mongodb+srv://elaraadmin:test0000@cluster0.kh4nl.mongodb.net/myFirstDatabase?retryWrites=true&w=majority"
}

# Required for cookie signing.
app.config["SECRET_KEY"] = "1a2b9bdd22abaed4d12e236c78afcb9a393ec15f71bbf5dc987d54727823bcc0"

# Required so that cookies are persisted by the Browser (especially Chrome) on cross origin clients.
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True

db = MongoEngine(app)
login = LoginManager(app)


# Adds headers to an API response needed -
# To be able to process API calls from cross origin clients.
# To tell clients that we support cookies.
def response_with_cors(response, request):
    response.headers.add("Access-Control-Allow-Origin",
                         request.environ.get("HTTP_ORIGIN", "*"))
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response


"""
Each Annotation is a time stamp and string contents.
"""


class Annotation(db.EmbeddedDocument):
    time_stamp = db.StringField()
    content = db.StringField()

    def to_json(self):
        return {
            "time_stamp": self.time_stamp,
            "content": self.content
        }


"""
The main object associated with a user. This will be stored in our database.
"""


class User(UserMixin, db.Document):
    # Auto incrementing id associatef with each object.
    uid = db.ObjectIdField(default=bson.ObjectId, primary_key=True)

    # Email. Always required.
    email = db.StringField()

    # Password hash associated with a user's password. It can be an empty string if the user has logged in via the OAuth flow.
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


# Used with flask-login to authenticate a User.
@login.user_loader
def load_user(id):
    return User.objects(uid=id).first()


# TODO: Used for debugging.
user = User.objects(email="maverick@gmail.com").first()
if not user:
    print("Creating new user")
    user = User(email="maverick@gmail.com",
                annotations={}, video_id_title_map={})
    user.set_password("foo1234!")
    user.save()

"""
This API is used to login a user via Google OAuth.

This API expects -
{
    'token' : <token>,
}
in the POST data.

It verifies this token via hitting the Google OAuth API. If the verification succeeds -
- If the user is new it creates a new user.
- If the user exists, it retrieves the existing user.

It then logs in the associated user and returns 200. Else returns a 400 error.
"""


@app.route("/v1/oauth/google/login", methods=["POST"])
def oauth_google_login():
    record = json.loads(request.data)
    token = record["token"]
    token_verification_response = requests.get(
        GOOGLE_OAUTH_TOKEN_VERIFICATION_URL, {GOOGLE_OAUTH_TOKEN_VERIFICATION_URL_TOKEN_QUERY_PARAMETER: token})
    if token_verification_response.status_code != requests.codes.ok:
        print("Error: Google OAuth token not verified")
        return response_with_cors(make_response(jsonify({"error": "google oauth token not verified"}), 400), request)

    token_verification_response_json = token_verification_response.json()
    if not token_verification_response_json.get("email_verified", False):
        print("Error: Google OAuth email not verified")
        return response_with_cors(make_response(jsonify({"error": "google oauth email not verified"}), 400), request)

    email = token_verification_response_json["email"]
    user = User.objects(email=email).first()
    if user is None:
        print("Creating new user with email: {}", email)
        user = User(email=email, password_hash="",
                    annotations={}, video_id_title_map={})
        user.save()

    print("Login user with email: {} after OAuth", email)
    login_user(user)
    return response_with_cors(jsonify({"msg": "success"}), request)


"""
This API is used to login a user via user name and password.

This API expects -
{
    'email' : <email>,
    'password': <password>,
}
in the POST data.

It tries to retrieve the user corresponding to the email and password.
- If the user exists it logs in the user and returns 200.
- If no user exists it returns a 400 error.
"""


@app.route("/v1/login", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return response_with_cors(jsonify(current_user.to_json()), request)

    record = json.loads(request.data)
    email = record.get("email", "")
    if not email:
        print("Error: Email Empty")
        return response_with_cors(make_response(jsonify({"error": "email empty"}), 400), request)

    password = record.get("password", "")
    if not password:
        print("Error: Password Empty")
        return response_with_cors(make_response(jsonify({"error": "password empty"}), 400), request)

    user = User.objects(email=email).first()
    if user is None or not user.check_password(password):
        print("Error: User doesn't exist or bad password")
        return response_with_cors(make_response(jsonify({"error": "invalid user or bad password"}), 400), request)

    print("Logging in user with email: {}", user.email)
    login_user(user)
    return response_with_cors(jsonify(user.to_json()), request)


"""
This API returns the list of videos for the current authenticated user.
"""


@app.route("/v1/list", methods=["GET"])
@login_required
def query_records():
    return response_with_cors(jsonify(user_videos=current_user.video_id_title_map), request)


"""
This API returns the annotations corresponding to a video for the current authenticated user.

This API expects "video_id=<video_id>" as a query parameter.

For e.g. for this Youtube URL https://www.youtube.com/watch?v=TcAAARgLZ8M the video id will be
"TcAAARgLZ8M".
"""


@app.route("/v1/annotations", methods=["GET"])
@login_required
def query_annotations():
    video_id = request.args.get("video_id", "")
    if not video_id:
        print("Error: Video Id empty")
        return response_with_cors(make_response(jsonify({"error": "Video Id empty"}), 400), request)
    return response_with_cors(jsonify(annotations=current_user.annotations[video_id]), request)


"""
This API adds an annotation associated with a video. It expects -
{
    'video_id' : <video_id>,
    'ts': <time_stamp>,
    'content': <content>,
    'video_title': <video_title>,
} in the POST data.
"""


@app.route("/v1/add", methods=["PUT"])
@login_required
def create_record():
    record = json.loads(request.data)
    # Id extracted from a Youtube URL.
    video_id = record.get("video_id", "")
    time_stamp = record.get("ts", "")
    content = record.get("content", "")
    video_title = record.get("video_title", "")
    print("video_id {} Ts {} Content {} video_title {}".format(
        video_id, time_stamp, content, video_title))

    if not video_id or not time_stamp or not content or not video_title:
        print("Error: Invalid Data")
        return response_with_cors(make_response(jsonify({"error": "Invalid Data"}), 400), request)

    # If the url has a "period" in it then mongo engine will complain while saving the object.
    # TODO: Same time stamps are added not updated.
    current_user.annotations.setdefault(video_id, []).append(Annotation(
        time_stamp=time_stamp, content=content))
    current_user.video_id_title_map[video_id] = video_title
    current_user.save()
    return response_with_cors(jsonify(current_user.to_json()), request)


"""
This API deletes all annotations associated with a video and all other metadata. It expects -
{
    'video_id' : <video_id>,
} in the body.
"""


@app.route("/v1/delete/video", methods=["DELETE"])
@login_required
def delete_video():
    record = json.loads(request.data)
    # Id extracted from a Youtube URL.
    video_id = record.get("video_id", "")
    if not video_id:
        print("Error: Invalid Data")
        return response_with_cors(make_response(jsonify({"error": "Invalid Data"}), 400), request)

    print("Delete Video video_id: {}".format(video_id))

    # First delete annotations for the video then delete it's title map.
    if not video_id in current_user.annotations:
        print("Annotations not found for video: {}".format(video_id))
        return response_with_cors(make_response(jsonify({"error": "Annotations not found for video"}), 400), request)
    # Safe to not catch exception as we do an explicit check before. We could have done if not
    # annotations.pop(video_id, None), but we won't be able to differentiate between an empty list
    # and a key error.
    current_user.annotations.pop(video_id)

    if not current_user.video_id_title_map.pop(video_id, None):
        print("Error: Failed to delete title for video: {}".format(video_id))
        return response_with_cors(make_response(jsonify({"error": "Failed to delete title for video"}), 400), request)

    current_user.save()
    return response_with_cors(jsonify({"msg": "success"}), request)


"""
This API deletes an annotation at a time stamp for a given video. It expects -
{
    'video_id' : <video_id>,
    'annotation_ts' : <time_stamp>,
} in the body.
"""


@app.route("/v1/delete/annotation", methods=["DELETE"])
@login_required
def delete_annotation():
    record = json.loads(request.data)
    # Id extracted from a Youtube URL.
    video_id = record.get("video_id", "")
    if not video_id:
        print("Error: Invalid video_id")
        return response_with_cors(make_response(jsonify({"error": "Invalid video_id"}), 400), request)

    annotation_ts = record.get("annotation_ts", "")
    if not video_id:
        print("Error: Invalid annotation ts")
        return response_with_cors(make_response(jsonify({"error": "Invalid ts"}), 400), request)

    print("Delete Annotation video_id: {} annotation_ts: {}".format(
        video_id, annotation_ts))

    if not video_id in current_user.annotations:
        print("Error: Failed to find video: {}".format(video_id))
        return response_with_cors(make_response(jsonify({"error": "Failed to find video"}), 400), request)
    annotations = current_user.annotations[video_id]

    # Filter all other annotations except the one at |time_stamp|.
    current_user.annotations[video_id] = [
        annotation for annotation in annotations if annotation["time_stamp"] != annotation_ts]

    current_user.save()
    return response_with_cors(jsonify({"msg": "success"}), request)


"""
This API logs out the currently authenticated user. Returns a 200 response.
"""


@app.route("/v1/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return response_with_cors(jsonify({"msg": "success"}), request)


if __name__ == "__main__":
    app.run(debug=True)
