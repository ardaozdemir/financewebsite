import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")



@app.route("/")
@login_required
def index():

    #Getting users stocks

    shares = db.execute("SELECT * FROM shares WHERE person_id = :user_id ORDER BY symbol DESC", user_id=session["user_id"])
    user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])

    #Creating a variable that keeps total money

    total_money = 0.0

    #Creating dictionaries to store price and name

    price_dict = {}
    name_dict = {}

    #Looping over user's stocks

    for i in range(len(shares)):
        stock = lookup(shares[i]["symbol"])
        shares[i]["symbol"] = stock["symbol"]
        price_dict[stock["symbol"]] = stock["price"]
        name_dict[stock["symbol"]] = stock["name"]
        total_money += shares[i]["share"] * stock["price"]

    #Storing the total money of the person with stocks values

    last_total = total_money + int(user[0]["cash"])


    return render_template("index.html", shares=shares, cash=usd(user[0]["cash"]), price_dict=price_dict, name_dict=name_dict, total_money = usd(total_money), last_total=last_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        #Checking if user entered a symbol or not

        if not request.form.get("symbol"):
            return apology("Must provide symbol", 403)

        #Checking if symbol exist on the API or not

        if lookup(request.form.get("symbol")) == None:
            return apology("This symbol doesn't exit", 403)

        #Checking if user entered positive number

        if int(request.form.get("shares")) < 1:
            return apology("Share amount should be positive", 403)

        #Assigning form inputs to the variables

        symbol = request.form.get("symbol").upper()

        value = lookup(request.form.get("symbol"))

        #Getting price of a stock

        stock_price = int(value["price"])

        #Getting information about user's shares and cash

        user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id= session["user_id"])

        user_share = db.execute("SELECT share FROM shares WHERE person_id = :user_id AND symbol= :symbol", user_id=session["user_id"], symbol=symbol)

        cash = user_cash[0]["cash"]

        #Getting the time

        when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        #Calculating the total transaction

        total_buy = int(request.form.get("shares")) * stock_price

        #Checking if user has enough money

        if total_buy > cash:
            return apology("You don't have enough money", 403)

        #If person has that stock just update

        if len(user_share) == 1:

            db.execute("UPDATE shares SET share = :share WHERE person_id = :user_id AND symbol = :symbol", share = user_share[0]["share"] + int(request.form.get("shares")), user_id = session["user_id"], symbol = symbol)

        #If person don't have this stock create a new stock

        else:

            db.execute("INSERT INTO shares (person_id, symbol, share) VALUES (:person_id , :symbol, :share)", person_id = int(session["user_id"]), symbol = symbol, share = int(request.form.get("shares")))

        #Adding this transaction to history database

        db.execute("INSERT INTO history (person_id, symbol, share, price, type, date) VALUES (:person_id , :symbol, :share, :price, :types, :date)", person_id = int(session["user_id"]), symbol = symbol, share = int(request.form.get("shares")),
        price = str(stock_price), types = "buy", date = when)

        #Updating user's cash

        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash = cash - total_buy, user_id = session["user_id"])

        return redirect("/")

    else:
        return render_template("buy.html")




@app.route("/history")
@login_required
def history():

    #Getting all of the history from the database

    history = db.execute("SELECT * FROM history WHERE person_id = :user_id ORDER BY date DESC", user_id=session["user_id"])


    return render_template("history.html", history = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))


        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


values = []

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":

        #Checking if user entered a symbol or not

        if not request.form.get("symbol"):
            return apology("Must provide symbol", 403)

        value = lookup(request.form.get("symbol"))

        values.append(value)

        return render_template("quoted.html", symbol=value["symbol"], name=value["name"], price=value["price"])

    else:

        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    session.clear()

    if request.method == "POST":

        #Checking if there is no username

        if not request.form.get("username"):
            return apology("Must provide username", 403)

        #Checking if there is no password

        if not request.form.get("password"):
            return apology("Must provide password", 403)

        #Checking if two password match or not

        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Password does not match")

        #Getting the usernames with users username input

        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        #Checking if the username exit

        if len(rows) == 1:

            return apology("Username was taken")

        #Saving user to the database

        if len(rows) != 1:

            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)" , username = request.form.get("username"), hash = generate_password_hash(request.form.get("password")))

        #Redirecting to the homepage

        return redirect("/")

    else:
        return render_template("register.html")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    if request.method == "POST":

        symbol = request.form.get("symbol").upper()

        #Checking form answers

        if not request.form.get("symbol"):
            return apology("Must provide symbol", 403)

        if lookup(request.form.get("symbol")) == None:
            return apology("This symbol doesn't exit", 403)

        if int(request.form.get("shares")) < 1:
            return apology("Share amount should be positive", 403)

        #Getting all details from the API

        value = lookup(request.form.get("symbol"))

        #Getting the current price for that share

        stock_price = int(value["price"])

        user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id= session["user_id"])

        user_share = db.execute("SELECT share FROM shares WHERE person_id = :user_id AND symbol= :symbol", user_id=session["user_id"], symbol=symbol)

        #Getting how much cash and share user have

        share = user_share[0]["share"]

        cash = user_cash[0]["cash"]

        #Getting the current time

        when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        #Calculating the total sell

        total_sell = int(request.form.get("shares")) * stock_price

        #Checking if user has enough shares to sell

        if share < int(request.form.get("shares")):
            return apology("You don't have enough share")


        #Adding it to the history database

        db.execute("INSERT INTO history (person_id, symbol, share, price, type, date) VALUES (:person_id , :symbol, :share, :price, :types, :date)", person_id = int(session["user_id"]), symbol = symbol, share = int(request.form.get("shares")),
        price = str(stock_price), types = "sell", date = when)

        #Updating user shares and cashes

        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash = cash + total_sell, user_id = session["user_id"])
        db.execute("UPDATE shares SET share = :share WHERE person_id = :user_id", share = share - int(request.form.get("shares")), user_id = session["user_id"])

        #Redirecting the homepage

        return redirect("/")

    else:
        return render_template("sell.html")

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():

    if request.method == "POST":

        #Checking if the two password same

        if request.form.get("password") == request.form.get("confirmation"):

            password = generate_password_hash(request.form.get("password"))

        #Updating the password

        db.execute("UPDATE users SET hash=:password WHERE id=:ids", password=password, ids= session["user_id"])

        return render_template("account.html", success=1)

    else:

        return render_template("account.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
