from functools import wraps

from flask import Flask, render_template, request, make_response, redirect, url_for
from firebase_admin._auth_utils import EmailAlreadyExistsError
from firebase_admin.exceptions import InvalidArgumentError
from werkzeug.exceptions import BadRequestKeyError
from dotenv import load_dotenv

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
            rememberme = request.form["rememberme"]
            data = fb.register_user(
                email=email,
                display_name=display_name,
                password=password,
                rememberme=rememberme,
            )

            resp = make_response(
                {
                    "status": "OK",
                    "message": "Registered successfully!",
                    "token": data["token"],
                }
            )
            resp.set_cookie("token", data["token"])
            return redirect(url_for(next), Response=resp)
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

            resp = make_response(redirect(url_for(next)))
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
        return redirect(url_for("listing", id=postId))
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
                response={"status": "OK", "message": "mangstap", "posts": posts},
            ),
            400,
        )
    except ValueError as e:
        return (
            render_template("listing", response={"status": "ERROR", "message": str(e)}),
            400,
        )


@app.route("/listing/<id>")
def post():
    return render_template("post.html")


if __name__ == "__main__":
    app.run()
