import os

from flask import Flask, session, render_template, request, redirect
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from tools import login_required

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    # Make sure that it is a new session
    session.clear()

    username = request.form.get("username")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if request.form.get("username") == None:
            return render_template("error.html", message="must provide username")

        # Ensure password was submitted
        elif request.form.get("password") == None:
            return render_template("error.html", message="must provide password")

        # Query database for account details
        rows = db.execute("SELECT * FROM public.user WHERE username = :username",
                            {"username": username})

        acc_details = rows.fetchone()

        # Ensure username exists and password is correct
        if acc_details == None or acc_details[1] != request.form.get("password"):
            return render_template("error.html", message="invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = acc_details[0] # needs fixing
        session["user_name"] = acc_details[0]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """ Register user """

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", message="must provide username")

        # Query database for username
        userCheck = db.execute("SELECT * FROM public.user WHERE username = :username",
                          {"username":request.form.get("username")}).fetchone()

        # Check if username already exist
        if userCheck:
            return render_template("error.html", message="username already exist")

        # Ensure password was submitted
        if not request.form.get("password"):
            return render_template("error.html", message="must provide password")

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return render_template("error.html", message="must confirm password")

        # Check passwords are equal
        elif not request.form.get("password") == request.form.get("confirmation"):
            return render_template("error.html", message="passwords didn't match")

        # Insert register into DB
        db.execute("INSERT INTO public.user (username, password) VALUES (:username, :password)",
                            {"username":request.form.get("username"),
                             "password":request.form.get("password")})

        # Commit changes to database
        db.commit()

        # Redirect user to login page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/logout")
def logout():
    """ Log user out """

    # Forget any user ID
    session.clear()

    # Redirect user to login form
    return redirect("/")
