from firebase_admin import initialize_app, credentials, firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin._auth_utils import EmailAlreadyExistsError
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequestKeyError
from os import getenv
from jose import jwt
import urllib.parse
import uuid
import time
import bcrypt
import json


class Firebase:
    def __init__(self):
        cred = credentials.Certificate(json.loads(getenv("FIREBASE_CREDENTIALS")))
        self.app = initialize_app(
            credential=cred,
            options={"storageBucket": "lost-and-found-19acb.appspot.com"},
        )
        self.firestore = firestore.client(app=self.app)
        self.storage = storage.bucket(app=self.app)

    def register_user(self, email: str, display_name: str, password: str):
        if not all([email, display_name, password]):
            raise BadRequestKeyError

        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")

        users_ref = self.firestore.collection("users")
        user = users_ref.where(filter=FieldFilter("email", "==", email)).get()

        if len(user) > 0:
            raise EmailAlreadyExistsError("Email already exists", email, 400)

        salt = bcrypt.gensalt()
        uid = str(uuid.uuid4())
        password = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        token = jwt.encode(
            claims={"uid": uid},
            key=getenv("JWT_PRIVATE"),
            algorithm="HS256",
            headers={"exp": time.time() + 3600},
        )

        users_ref.add(
            {
                "uid": uid,
                "email": email,
                "display_name": display_name,
                "password": password,
                "photo_url": f"https://api.dicebear.com/7.x/thumbs/svg?seed={urllib.parse.quote(display_name)}",
            }
        )
        return {"token": token}

    def login_user(self, email: str, password: str, rememberme: bool = False):
        if not all([email, password]):
            raise BadRequestKeyError

        users_ref = self.firestore.collection("users")
        user = users_ref.where("email", "==", email).get()

        if len(user) == 0:
            raise ValueError("User not found")

        user_dict = user[0].to_dict()

        if not bcrypt.checkpw(
            password.encode("utf-8"), user_dict["password"].encode("utf-8")
        ):
            raise ValueError("Incorrect password")

        token = jwt.encode(
            claims={"uid": user_dict["uid"]},
            key=getenv("JWT_PRIVATE"),
            algorithm="HS256",
            headers={
                "exp": time.time() + (3600 * 24 * 30)
                if rememberme
                else time.time() + 3600
            },
        )
        return {"token": token}

    def token_is_valid(self, token: str):
        try:
            jwt.decode(token, getenv("JWT_PRIVATE"), algorithms="HS256")
            return True
        except:
            return False

    def get_user_info(self, uid: str):
        users_ref = self.firestore.collection("users")
        user = users_ref.where("id", "==", uid).get()[0].to_dict()

        if user is None:
            raise ValueError("User not found")

        user["comments"] = self.get_comments_by_uid(uid)
        user["posts"] = self.get_posts_by_uid(uid)

        return user

    def get_posts(self):
        posts_ref = self.firestore.collection("posts")
        posts = posts_ref.get()
        return [post.to_dict() for post in posts]

    def get_post_by_id(self, post_id: str):
        posts_ref = self.firestore.collection("posts")
        post = (
            posts_ref.where(filter=FieldFilter("id", "==", post_id)).get()[0].to_dict()
        )
        return post

    def get_posts_by_uid(self, uid: str):
        posts_ref = self.firestore.collection("posts")
        posts = posts_ref.where("uid", "==", uid).get()
        return [post.to_dict() for post in posts]

    def get_comments_by_post_id(self, post_id: str):
        comments_ref = self.firestore.collection("comments")
        comments = comments_ref.where("post_id", "==", post_id).get()
        nested_comments = []

        for comment in comments:
            comment_dict = comment.to_dict()

            if "reply_to" in comment_dict:
                parent_comment_id = comment_dict["reply_to"]
                parent_comment = comments_ref.document(parent_comment_id).get()
                parent_comment_dict = parent_comment.to_dict()

                if "comments" not in parent_comment_dict:
                    parent_comment_dict["comments"] = []

                parent_comment_dict["comments"].append(comment_dict)
                parent_comment.reference.update(
                    {"comments": parent_comment_dict["comments"]}
                )
            else:
                nested_comments.append(comment_dict)

        return nested_comments

    def get_comments_by_uid(self, uid: str):
        comments_ref = self.firestore.collection("comments")
        comments = comments_ref.where("uid", "==", uid).get()
        return [comment.to_dict() for comment in comments]

    def create_listing(
        self, title: str, body: str, attachment: FileStorage, token: str
    ):
        if not all([title, body]):
            raise BadRequestKeyError

        attachment_url = self.upload_file(attachment) if attachment else None

        posts_ref = self.firestore.collection("posts")
        # from jwt decode it and get the uid
        uid = self.get_uid_from_token(token)
        post_id = str(uuid.uuid4())
        posts_ref.add(
            {
                "id": post_id,
                "title": title,
                "body": body,
                "post_owner": uid,
                "post_date": time.time(),
                "attachment_url": attachment_url,
            }
        )
        return post_id

    def upload_file(self, file: FileStorage):
        blob = self.storage.blob(file.filename)
        blob.upload_from_file(file.stream)
        blob.make_public()
        return blob.public_url

    def get_uid_from_token(self, token: str):
        return jwt.decode(token, getenv("JWT_PRIVATE"), algorithms="HS256")["uid"]
