from flask import Flask, render_template, request, make_response, redirect, url_for
from firebase_admin._auth_utils import EmailAlreadyExistsError
from firebase_admin.exceptions import InvalidArgumentError
from werkzeug.exceptions import BadRequestKeyError
from Firebase import Firebase
from dotenv import load_dotenv
from functools import wraps

load_dotenv('./firebase.env')

app = Flask(__name__)
fb = Firebase()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('token')
        if fb.token_is_valid(token) is False:
            return redirect(url_for('login', next=f.__name__))
        else:
            return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            if not request.form['firstp'] == 'qwerasdfzxcv':
                raise Exception("gtfo")
            fb.delete_temp_acct()
            return render_template("index.html", r={ 's': 'yes' })
        except Exception as e:
            return render_template("index.html", r={ 's': str(e) })
    elif request.method == 'GET':
        return render_template("index.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form['email']
            display_name = request.form['username']
            password = request.form['password']
            token = fb.register_user(email=email, display_name=display_name, password=password)
            
            resp = make_response({ 'status': 'OK', 'message': 'Registered successfully!', 'token': token })
            resp.set_cookie('token', token)
            return redirect(url_for(request.args.get('next'), token=token))
        except BadRequestKeyError:
            return render_template("register.html", response = { 'status': 'ERROR', 'message': 'All fields are required!' }), 400
        except EmailAlreadyExistsError:
            return render_template("register.html", response = { 'status': 'ERROR', 'message': 'Email already exists!' }), 400
        except InvalidArgumentError as e:
            return render_template("register.html", response = { 'status': 'ERROR', 'message': str(e) }), 400
        except ValueError as e:
            return render_template("register.html", response = { 'status': 'ERROR', 'message': str(e) }), 400
    elif request.method == 'GET':
        return render_template("register.html", response = {}), 200

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            display_name = request.form['username']
            password = request.form['password']
            token = fb.authenticate_login(display_name=display_name, password=password)
            
            resp = make_response({ 'status': 'OK', 'message': 'Logged in successfully!', 'token': token })
            resp.set_cookie('token', token)
            return redirect(url_for(request.args.get('next')))
        except BadRequestKeyError:
            return render_template("login.html", response = { 'status': 'ERROR', 'message': 'All fields are required!' }), 400
        except InvalidArgumentError as e:
            return render_template("login.html", response = { 'status': 'ERROR', 'message': str(e) }), 400
        except ValueError as e:
            return render_template("login.html", response = { 'status': 'ERROR', 'message': str(e) }), 400
    elif request.method == 'GET':
        return render_template("login.html", response = {}), 200

@app.route("/report")
@login_required
def report():
    return render_template("report.html")

@app.route("/lost_items")
@login_required
def listing():
    return render_template("items-list.html")

if __name__ == "__main__":
    app.run()
