from functools import wraps

from flask import Flask, render_template, request, make_response, redirect, url_for
from firebase_admin._auth_utils import EmailAlreadyExistsError
from firebase_admin.exceptions import InvalidArgumentError
from werkzeug.exceptions import BadRequestKeyError
from dotenv import load_dotenv
import time

from Firebase import Firebase

load_dotenv()

app = Flask(__name__)
fb = Firebase()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get("token")
        if fb.token_is_valid(token) is False:
            return redirect(url_for("login", next=f.__name__))
        else:
            return f(*args, **kwargs)

    return decorated_function


@app.template_filter("time")
def datetimeformat(value, format="%H:%M / %d-%m-%Y"):
    return time.strftime(format, time.localtime(value))


@app.context_processor
def utility_processor():
    def get_user_from_id(id):
        return fb.get_user_info(id)
    def get_current_uid():
        return fb.get_decoded_token(request.cookies.get("token"))["uid"]

    return dict(get_user_from_id=get_user_from_id, get_current_uid=get_current_uid)



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    next = request.args.get("next") if request.args.get("next") else "index"
    if request.method == "POST":
        try:
            email = request.form["email"]
            display_name = request.form["username"]
            password = request.form["password"]
            data = fb.register_user(
                email=email,
                display_name=display_name,
                password=password,
            )

            resp = make_response(
                redirect(url_for(next)),
                {
                    "status": "OK",
                    "message": "Registered successfully!",
                    "token": data["token"],
                },
            )
            resp.set_cookie("token", data["token"])
            return resp
        except BadRequestKeyError:
            return (
                render_template(
                    "register.html",
                    response={"status": "ERROR", "message": "All fields are required!"},
                ),
                400,
            )
        except EmailAlreadyExistsError:
            return (
                render_template(
                    "register.html",
                    response={"status": "ERROR", "message": "Email already exists!"},
                ),
                400,
            )
        except InvalidArgumentError as e:
            return (
                render_template(
                    "register.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )
        except ValueError as e:
            return {"status": "ERROR", "message": str(e)}, 400
    elif request.method == "GET":
        if fb.token_is_valid(request.cookies.get("token")):
            return redirect(url_for(next))
        else:
            return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    next = request.args.get("next") if request.args.get("next") else "index"
    if request.method == "POST":
        try:
            email = request.form["email"]
            password = request.form["password"]
            rememberme = True if request.form.get("rememberme") else False
            data = fb.login_user(email=email, password=password, rememberme=rememberme)

            resp = make_response(
                redirect(url_for(next)),
                {
                    "status": "OK",
                    "message": "Registered successfully!",
                    "token": data["token"],
                },
            )
            resp.set_cookie("token", data["token"])
            return resp
        except InvalidArgumentError as e:
            return (
                render_template(
                    "login.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )
        except ValueError as e:
            return (
                render_template(
                    "login.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )
    elif request.method == "GET":
        if fb.token_is_valid(request.cookies.get("token")):
            return redirect(url_for(next))
        else:
            return render_template("login.html")


@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        attachment = request.files["attachment"]
        token = request.cookies.get("token")
        postId = fb.create_listing(
            title=title, body=body, attachment=attachment, token=token
        )
        return redirect("/listing/" + postId)
    elif request.method == "GET":
        return render_template("report.html")


@app.route("/listing")
@login_required
def listing():
    try:
        posts = fb.get_posts()

        if len(posts) == 0:
            raise ValueError("There are no posts")

        return (
            render_template(
                "listing.html",
                response={"status": "OK", "posts": posts},
            ),
            400,
        )
    except ValueError as e:
        return (
            render_template(
                "listing.html", response={"status": "ERROR", "message": str(e)}
            ),
            400,
        )


@app.route("/listing/<id>")
def post(id):
    post = fb.get_post_by_id(id)
    return (
        render_template("post.html", response={"status": "OK", "post": post}),
        400,
    )


@app.route("/listing/<id>/edit", methods=["GET", "POST"])
def post_edit(id):
    unedited_post = fb.get_post_by_id(id)
    if request.method == "POST":
        try:
            title = request.form["title"]
            body = (
                request.form["body"] if request.form["body"] else unedited_post["body"]
            )
            attachment = (
                request.files["attachment"]
                if request.files["attachment"]
                else unedited_post["attachment_url"]
            )
            token = request.cookies.get("token")
            postId = fb.update_listing(
                title=title, body=body, attachment=attachment, token=token, post_id=id
            )
            return redirect("/listing/" + postId)
        except BadRequestKeyError:
            return (
                render_template(
                    "editpost.html",
                    response={"status": "ERROR", "message": "All fields are required!"},
                ),
                400,
            )
        except ValueError as e:
            return (
                render_template(
                    "editpost.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )
    elif request.method == "DELETE":
        try:
            token = request.cookies.get("token")
            fb.delete_listing(id, token)
            return redirect("/listing")
        except ValueError as e:
            return (
                render_template(
                    "editpost.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )
    elif request.method == "GET":
        try:
            post = fb.get_post_by_id(id)
            return (
                render_template(
                    "editpost.html", response={"status": "OK", "post": post}
                ),
                400,
            )
        except ValueError as e:
            return (
                render_template(
                    "editpost.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )


@app.route("/listing/<id>/delete", methods=["POST"])
def post_delete(id):
    if request.method == "POST":
        try:
            token = request.cookies.get("token")
            fb.delete_listing(id, token)
            return redirect("/listing")
        except ValueError as e:
            return (
                render_template(
                    "editpost.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "GET":
        user = fb.get_user_info(
            fb.get_decoded_token(request.cookies.get("token"))["uid"]
        )
        return render_template("account.html", data=user)
    elif request.method == "POST":
        if request.cookies.get("token"):
            resp = make_response(
                redirect(url_for("index")),
                {
                    "status": "ALERT",
                    "message": "Logged out",
                },
            )
            resp.set_cookie("token", "")
            return resp
        else:
            return make_response({"status": "ERROR", "message": "Not logged in"})


@app.route("/profile/<id>")
def user(id):
    user = fb.get_user_info(id)
    return render_template("profile.html", data=user)


@app.route("/listing/<id>/comment", methods=["POST", "DELETE"])
def comment(id):
    if request.method == "POST":
        try:
            body = request.form["comment"]
            token = request.cookies.get("token")
            fb.create_comment(body=body, token=token, post_id=id)
            return redirect("/listing/" + id)
        except BadRequestKeyError:
            return (
                render_template(
                    "listing.html",
                    response={"status": "ERROR", "message": "All fields are required!"},
                ),
                400,
            )
        except ValueError as e:
            return (
                render_template(
                    "listing.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )
    elif request.method == "DELETE":
        try:
            token = request.cookies.get("token")
            fb.delete_comment(id, token)
            return redirect("/listing/" + id)
        except ValueError as e:
            return (
                render_template(
                    "listing.html", response={"status": "ERROR", "message": str(e)}
                ),
                400,
            )


@app.route("/listing/<id>/comment/<comment_id>", methods=["POST"])
def reply(id, comment_id):
    try:
        body = request.form["comment"]
        token = request.cookies.get("token")
        fb.create_comment(body=body, token=token, post_id=id, reply_to=comment_id)
        return redirect("/listing/" + id)
    except BadRequestKeyError:
        return (
            render_template(
                "listing.html",
                response={"status": "ERROR", "message": "All fields are required!"},
            ),
            400,
        )
    except ValueError as e:
        return (
            render_template(
                "listing.html", response={"status": "ERROR", "message": str(e)}
            ),
            400,
        )


if __name__ == "__main__":
    app.run()
