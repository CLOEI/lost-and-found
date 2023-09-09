from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/report")
def report():
    return render_template("report.html")


@app.route("/lost_items")
def listing():
    return render_template("items-list.html")


if __name__ == "__main__":
    app.run()
