import os
from datetime import datetime
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

with app.app_context():
    init_db()
    seed_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm_password:
        return render_template(
            "register.html",
            error="All fields are required.",
            name=name,
            email=email,
        ), 400

    if len(password) < 8:
        return render_template(
            "register.html",
            error="Password must be at least 8 characters.",
            name=name,
            email=email,
        ), 400

    if password != confirm_password:
        return render_template(
            "register.html",
            error="Passwords do not match.",
            name=name,
            email=email,
        ), 400

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        conn.close()
        return render_template(
            "register.html",
            error="An account with this email already exists.",
            name=name,
            email=email,
        ), 400

    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "login.html",
            error="Email and password are required.",
            email=email,
        ), 400

    conn = get_db()
    user = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html",
            error="Invalid email or password.",
            email=email,
        ), 400

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = email

    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/profile")
@login_required
def profile():
    conn = get_db()

    db_user = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()

    if db_user is None:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    name = db_user["name"]
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "U"
    created_at = datetime.strptime(db_user["created_at"], "%Y-%m-%d %H:%M:%S")
    user = {
        "name": name,
        "email": db_user["email"],
        "member_since": created_at.strftime("%B %Y"),
        "initials": initials,
    }

    totals = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
        FROM expenses WHERE user_id = ?
        """,
        (session["user_id"],),
    ).fetchone()
    total_spent = totals["total"]

    top_category_row = conn.execute(
        """
        SELECT category FROM expenses WHERE user_id = ?
        GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1
        """,
        (session["user_id"],),
    ).fetchone()
    stats = {
        "total_spent": total_spent,
        "transaction_count": totals["count"],
        "top_category": top_category_row["category"] if top_category_row else "—",
    }

    transaction_rows = conn.execute(
        """
        SELECT date, description, category, amount FROM expenses
        WHERE user_id = ? ORDER BY date DESC LIMIT 5
        """,
        (session["user_id"],),
    ).fetchall()
    transactions = [
        {
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d-%m-%Y"),
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in transaction_rows
    ]

    category_rows = conn.execute(
        """
        SELECT category, SUM(amount) AS total FROM expenses
        WHERE user_id = ? GROUP BY category ORDER BY total DESC
        """,
        (session["user_id"],),
    ).fetchall()
    categories = [
        {
            "name": row["category"],
            "total": row["total"],
            "percent": round(row["total"] / total_spent * 100) if total_spent else 0,
        }
        for row in category_rows
    ]

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
