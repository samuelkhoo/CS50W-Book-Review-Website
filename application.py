import os

from flask import Flask, session, render_template, request, redirect, flash, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from tools import login_required

import requests
import json

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

# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    # Make sure that it is a new session
    session.clear()

    # Submit registration request
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", message="Username not provided")

        # Query database for username
        userCheck = db.execute("SELECT * FROM public.users WHERE username = :username",
                          {"username":request.form.get("username")}).fetchone()

        # Check if username already exist
        if userCheck:
            return render_template("error.html", message="Username already taken")

        # Ensure password was submitted
        if not request.form.get("password"):
            return render_template("error.html", message="Password not provided")

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return render_template("error.html", message="Password not confirmed")

        # Check passwords are equal
        elif not request.form.get("password") == request.form.get("confirmation"):
            return render_template("error.html", message="Passwords do not match")

        # Insert register into DB
        db.execute("INSERT INTO public.users (username, password) VALUES (:username, :password)",
                            {"username":request.form.get("username"),
                             "password":request.form.get("password")})

        # Commit changes to database
        db.commit()

        # Redirect user to login page
        return redirect("/login")

    # View register page
    else:
        return render_template("register.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    # Make sure that it is a new session
    session.clear()

    username = request.form.get("username")

    # Submit login attempt
    if request.method == "POST":

        # Ensure username was submitted
        if request.form.get("username") == None:
            return render_template("error.html", message="Username not provided")

        # Ensure password was submitted
        elif request.form.get("password") == None:
            return render_template("error.html", message="Password not provided")

        # Query database for account details
        rows = db.execute("SELECT * FROM public.users WHERE username = :username",
                            {"username": username})

        acc_details = rows.fetchone()

        # Ensure username exists and password is correct
        if acc_details == None or acc_details[2] != request.form.get("password"):
            return render_template("error.html", message="Username and/or password is incorrect")

        # Remember which user has logged in
        session["user_id"] = acc_details[0]
        session["user_name"] = acc_details[1]

        # Redirect user to index page
        return redirect("/")

    # View login page
    else:
        return render_template("login.html")

# Home page
@app.route("/")
@login_required
def index():
    return render_template("index.html")

# Search results
@app.route("/search", methods=["GET"])
@login_required
def search():

    # Check book id was provided
    if not request.args.get("book"):
        return render_template("error.html", message="Book not provided")

    # query
    q = "%" + request.args.get("book") + "%"

    # Capitalize all letters so that search is not case sensitive
    q = q.title()

    result = db.execute("SELECT isbn, title, author, year, id FROM books WHERE isbn LIKE :q OR title LIKE :q OR author LIKE :q OR year LIKE :q",
                {"q": q})

    # Handle no results
    if result.rowcount == 0:
        return render_template("error.html", message="Book not found")

    # Fetch all the results
    books = result.fetchall()

    return render_template("result.html", books=books)

# Book details
@app.route("/book/<isbn>", methods=['GET','POST'])
@login_required
def book(isbn):
    # Submit book review
    if request.method == "POST":

        # Save current user info
        currentUser = session["user_id"]

        # Fetch form data
        rating = int(request.form.get("rating"))
        review = request.form["review"]

        # Search book_id by ISBN
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        # Save id into variable
        bookId = row.fetchone() # (id,)
        bookId = bookId[0]

        # Check if user made a review before
        row2 = db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                    {"user_id": currentUser,
                     "book_id": bookId})

        if row2.rowcount == 1:

            flash('Review submitted before. Only one review can be submitted.')
            return redirect("/book/" + isbn)

        db.execute("INSERT INTO reviews (user_id, book_id, review, rating) VALUES (:user_id, :book_id, :review, :rating)",
                    {"user_id": currentUser,"book_id": bookId,"review": review,"rating": rating})

        # Commit transactions to DB and close the connection
        db.commit()

        flash('Review submitted!', 'info')

        return redirect("/book/" + isbn)

    # View book page
    else:

        row = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn = :isbn",
                        {"isbn": isbn})

        book_info = row.fetchall()

        # Read API key from env variable
        key = "xAwinsHHQuJPipsPWJu9w"

        # Query the goodreads api
        query = requests.get("https://www.goodreads.com/book/review_counts.json",
                params={"key": key, "isbns": isbn})

        # Convert the response to JSON
        response = query.json()

        # Append it to book_info
        book_info.append(response['books'][0])

         # Get book_id from database using ISBN
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        # Save book_id as a variable
        book = row.fetchone()[0]

        # Fetch book reviews
        results = db.execute("SELECT users.username, review, rating FROM users INNER JOIN reviews ON users.id = reviews.user_id WHERE book_id = :book",
                            {"book": book})

        reviews = results.fetchall()

        return render_template("book.html", book_info=book_info, reviews=reviews)

# logout
@app.route("/logout")
def logout():

    # Forget any user ID
    session.clear()

    # Redirect user to login form
    return redirect("/")

# api
@app.route("/api/<isbn>", methods=['GET'])
@login_required
def api_call(isbn):

    query = db.execute("SELECT title, author, year, isbn, COUNT(reviews.id) as review_count, AVG(reviews.rating) as average_score FROM books INNER JOIN reviews ON books.id = reviews.book_id WHERE isbn = :isbn GROUP BY title, author, year, isbn",
                    {"isbn": isbn})

    # Handle error
    if query.rowcount !=1:
        return jsonify({"Error": "Invalid ISBN"}), 404

    # Get result
    row = query.fetchone()

    # Convert to dict
    result = dict(row.items())

    # Round average_score to 2 decimal
    result['average_score'] = float('%.2f'%(result['average_score']))

    return jsonify(result)
