import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime

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
    """Show portfolio of stocks"""
    # Get the number of shares the user currently owns
    whatIHave = db.execute(
        "SELECT symbol, company, SUM(quantity) AS qty, price, total FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])

    # List to store stocks information
    stocks_information = []
    # Sum of totals
    sumtotals = 0

    # Create variables and append to the dictionary with the information to display.
    for stock in whatIHave:
        # If user has more than 0 shares
        if stock.get("qty") > 0:
            current_price = lookup(stock.get("symbol"))  # Get the current price of the shares
            symbol = stock.get("symbol")
            # company = stock.get("company")
            qty = stock.get("qty")
            # Get the total
            price = current_price.get("price")
            total = price * stock.get("qty")
            # Give usd format to price and total
            stock["price"] = usd(price)
            stock["total"] = usd(total)
            # Append to the dictionary
            stocks_information.append(stock)
            # Sum totals to get the final grand total
            sumtotals += total

        # If users sold all their shares
        else:
            continue

    # Get the sum of the cash
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    # Get the sum of the total
    balance = cash[0]["cash"]
    grandtotal = balance + sumtotals

    # Display the information in the "/" route
    return render_template("index.html", cash=usd(cash[0]["cash"]), stocks_information=stocks_information, grandtotal=grandtotal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST
    if request.method == "POST":

        # Use the lookup function to compare the symbols in the Python dictionary
        quote = lookup(request.form.get("symbol"))

        # Store the number of desired shares
        shares = request.form.get("shares")

        # If the symbol is not in the dictionary
        if quote == None:
            return apology("Invalid Symbol", 400)

        # Check for a valid number of shares to buy
        if not shares:
            return apology("Input a positive number of shares greater than 0", 400)

        # Check for invalid input
        if not shares.isdigit():
            return apology("Input a numeric number", 400)

        # Calculate the value of the desired shares
        price = quote.get("price")
        total = price * int(shares)

        # Verify if the purchase is affordable
        # Check user balance
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # Compare the available cash to the price of the desired purchase
        if total > cash[0]["cash"]:
            return apology("Not enough cash", 403)

        # If the user has enough money to afford the purchase
        else:
            time = datetime.now()
            symbol = request.form.get("symbol")
            quantity = int(shares)
            balance = cash[0]["cash"] - total
            company = quote.get("name")

            # Insert the transaction in the history record
            db.execute("INSERT INTO transactions (user_id, symbol, quantity, price, time, total, company) VALUES (:user_id, :symbol, :quantity, :price, :time, :total, :company)",
                       user_id=session["user_id"], symbol=symbol, quantity=quantity, price=quote["price"], time=time, total=total, company=company)

            # Subtract the purchase from cash of the current user
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=balance, id=session["user_id"])

            # Flash message
            flash("Bought!")

            return redirect("/")

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, quantity, price, time FROM transactions WHERE user_id = ?", session["user_id"])

    # Add $ to each price
    for transaction in transactions:
        transaction["price"] = usd(transaction["price"])

    return render_template("history.html", transactions=transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Logged in!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


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
    """Get stock quote."""
    # User reached route via POST
    if request.method == "POST":

        # Use the lookup function to compare the symbols in the Python dictionary
        quote = lookup(request.form.get("symbol"))

        # If the symbol is not in the dictionary
        if quote == None:
            return apology("Invalid Symbol", 400)

        # If the symbol is in the dictionary
        else:
            name = quote.get("name")
            symbol = quote.get("symbol")
            price = quote.get("price")
            flash("Current Share Price!")
            return render_template("quoted.html", name=name, symbol=symbol, price=usd(price))

    # User reached route via GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached via POST
    if request.method == "POST":

        # Ensure a username is provided
        if not request.form.get("username"):
            return apology("Must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 400)

        # Ensure password is re-typed
        elif not request.form.get("confirmation"):
            return apology("Re-type your password", 400)

        # Ensure passwords are identical
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords must be identical", 400)

        # Generate a hashed password from the user's input information
        hashed = generate_password_hash(request.form.get("password"))
        username = request.form.get("username")

        # Add username and hashed password to the users table.
        try:
            information = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed)
        except:
            # If the username already exists.
            return apology("Username already in use", 400)

        # Start session
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Succesfylly Registered!")
        return redirect("/")

    # User reached via POST
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Variable to calculate the total number of shares owned from a specific company
    stocks = db.execute("SELECT symbol, SUM(quantity) FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])

    # User reached route via POST
    if request.method == "POST":

        # Store the number of shares to sell and symbol to choose
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        ownedshares = db.execute(
            "SELECT SUM(quantity) AS qty FROM transactions WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)

        # Check user balance
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # Error if the user doesn't input a symbol or number of shares to sell
        if not symbol:
            return apology("Select a symbol from your stocks", 400)
        if not shares:
            return apology("Input a positive number of shares greater than 0", 400)

        # Verify if the number of shares to sell is minor or equal to the shares owned
        if int(shares) > ownedshares[0]["qty"]:
            return apology("Not enough shares to sell", 400)

        # Multiply the current shares quote with the number of shares sold
        quote = lookup(request.form.get("symbol"))
        price = quote.get("price")
        total = int(shares) * price

        # Update "/history" using negative numbers to indicate the sold shares.
        quantity = int(shares) * -1  # Negative number to indicate sold shares.
        time = datetime.now()
        company = quote.get("name")
        db.execute("INSERT INTO transactions (user_id, symbol, quantity, price, time, total, company) VALUES (:user_id, :symbol, :quantity, :price, :time, :total, :company)",
                   user_id=session["user_id"], symbol=symbol, quantity=quantity, price=quote["price"], time=time, total=total, company=company)

        # Update cash and shares
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        balance = cash[0]["cash"] + total
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=balance, id=session["user_id"])

        flash("Sold!")
        return redirect("/")

    # User reached route via GET
    else:
        # Create a dropdown list with the shares owned by the user
        symbols = []
        for stock in stocks:
            symbols.append(stock.get("symbol"))

        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
