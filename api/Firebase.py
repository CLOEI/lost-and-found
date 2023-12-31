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
from typing import Union


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
            claims={"uid": uid, "display_name": display_name},
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

        if not bcrypt.checkpw(password.encode("utf-8"), user_dict["password"].encode("utf-8")):
            raise ValueError("Incorrect password")

        token = jwt.encode(
            claims={"uid": user_dict["uid"], "display_name": user_dict["display_name"]},
            key=getenv("JWT_PRIVATE"),
            algorithm="HS256",
            headers={"exp": time.time() + (3600 * 24 * 30) if rememberme else time.time() + 3600},
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
        user = users_ref.where(filter=FieldFilter("uid", "==", uid)).get()

        if len(user) == 0:
            raise ValueError("User not found")

        user = user[0].to_dict()

        user["comments"] = self.get_comments_by_uid(uid)
        user["posts"] = self.get_posts_by_uid(uid)

        return user

    def get_username_only(self, uid: str):
        users_ref = self.firestore.collection("users")
        user = users_ref.where(filter=FieldFilter("uid", "==", uid)).get()

        if len(user) == 0:
            raise ValueError("User not found")

        dn = user[0].to_dict()["display_name"]

        return dn

    def get_posts(self):
        posts_ref = self.firestore.collection("posts")
        posts = posts_ref.order_by("post_date", direction=firestore.Query.DESCENDING).get()
        return [post.to_dict() for post in posts]

    def get_post_by_id(self, post_id: str):
        posts_ref = self.firestore.collection("posts")
        post = posts_ref.where(filter=FieldFilter("id", "==", post_id)).get()[0].to_dict()
        post["comments"] = self.get_comments_by_post_id(post_id)
        return post

    def get_posts_by_uid(self, uid: str):
        posts_ref = self.firestore.collection("posts")
        posts = posts_ref.where(filter=FieldFilter("post_owner_uid", "==", uid)).get()
        return [post.to_dict() for post in posts]

    def get_comments_by_post_id(self, post_id: str):
        comments_ref = self.firestore.collection("comments")
        comments = comments_ref.where(filter=FieldFilter("post_id", "==", post_id)).order_by("comment_date", direction=firestore.Query.DESCENDING).get()
        nested_comments = []

        for comment in comments:
            comment_dict = comment.to_dict()

            if comment_dict["reply_to"]:
                parent_comment_id = comment_dict["reply_to"]
                parent_comment = comments_ref.where("id", "==", parent_comment_id).get()
                parent_comment_dict = parent_comment.to_dict()

                if not parent_comment:
                    continue

                if "comments" not in parent_comment_dict:
                    parent_comment_dict["comments"] = []

                parent_comment_dict["comments"].append(comment_dict)
                parent_comment.reference.update({"comments": parent_comment_dict["comments"]})
            else:
                nested_comments.append(comment_dict)

        return nested_comments

    def get_comments_by_uid(self, uid: str):
        comments_ref = self.firestore.collection("comments")
        comments = comments_ref.where("uid", "==", uid).order_by("comment_date", direction=firestore.Query.DESCENDING).get()
        return [comment.to_dict() for comment in comments]

    def create_listing(self, title: str, body: str, attachment: FileStorage, token: str):
        if not all([title, body]):
            raise BadRequestKeyError

        attachment_url = self.upload_file(attachment) if attachment else None

        posts_ref = self.firestore.collection("posts")
        # from jwt decode it and get the uid
        decoded = self.get_decoded_token(token)
        post_id = str(uuid.uuid4())
        posts_ref.add(
            {
                "id": post_id,
                "title": title,
                "body": body,
                "post_owner_uid": decoded["uid"],
                "post_owner_name": decoded["display_name"],
                "post_date": time.time(),
                "attachment_url": attachment_url,
            }
        )
        return post_id

    def delete_listing(self, post_id: str, token: str):
        decoded = self.get_decoded_token(token)
        posts_ref = self.firestore.collection("posts")
        post = posts_ref.where(filter=FieldFilter("id", "==", post_id)).get()[0]
        post_dict = post.to_dict()
        if post_dict["post_owner_uid"] != decoded["uid"]:
            raise ValueError("You are not the owner of this post")

        post.reference.delete()
        return True

    def update_listing(
        self,
        title: str,
        body: str,
        attachment: Union[str, FileStorage],
        token: str,
        post_id: str,
    ):
        if not all([title, body]):
            raise BadRequestKeyError

        attachment_url = self.upload_file(attachment) if type(attachment) is FileStorage else attachment

        posts_ref = self.firestore.collection("posts")

        decoded = self.get_decoded_token(token)

        post = posts_ref.where(filter=FieldFilter("id", "==", post_id)).get()[0]

        if post.to_dict()["post_owner_uid"] != decoded["uid"]:
            raise ValueError("You are not the owner of this post")

        post.reference.update(
            {
                "title": title,
                "body": body,
                "post_owner_uid": decoded["uid"],
                "post_owner_name": decoded["display_name"],
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

    def get_decoded_token(self, token: str):
        return jwt.decode(token, getenv("JWT_PRIVATE"), algorithms="HS256")

    def create_comment(self, body: str, token: str, post_id: str, reply_to: str = None):
        if not all([body]):
            raise BadRequestKeyError

        decoded = self.get_decoded_token(token)
        comments_ref = self.firestore.collection("comments")
        comment_id = str(uuid.uuid4())
        comments_ref.add(
            {
                "id": comment_id,
                "body": body,
                "post_id": post_id,
                "uid": decoded["uid"],
                "display_name": decoded["display_name"],
                "comment_date": time.time(),
                "reply_to": reply_to,
            }
        )
        return comment_id

    def delete_comment(self, comment_id: str, token: str):
        decoded = self.get_decoded_token(token)
        comments_ref = self.firestore.collection("comments")
        comment = comments_ref.where(filter=FieldFilter("id", "==", comment_id)).get()[0]
        comment_dict = comment.to_dict()
        if comment_dict["uid"] != decoded["uid"]:
            raise ValueError("You are not the owner of this comment")

        comment.reference.delete()
        return True
