"""
Tests for the Spendly "Add Expense" feature (Step 7).

Spec: .claude/specs/07-add-expense.md

`/expenses/add` gains a GET (render the add-expense form) and POST (validate +
insert) handler backed by a new `insert_expense(user_id, amount, category,
date, description)` helper in `database/queries.py`. On success the user is
redirected to `/profile`; on any validation failure the form is re-rendered
(200) with an error message and the previously submitted values retained.

These tests are derived strictly from the spec's described routes,
validation rules, and "Tests to write" table. `app.py` and `database/db.py`
were only consulted for structural conventions needed to make the tests
runnable: route names/paths, the `login_required` -> redirect-to-`/login`
pattern, the `users`/`expenses` table schema, `get_db()`'s `DB_PATH`
resolution, and the existence/signature of `database.queries.insert_expense`.
No assertions were derived from reading `add_expense`'s route body.
"""

import os
import tempfile

import pytest

import database.db as db_module

# ``app.py`` calls ``init_db()`` / ``seed_db()`` at *import* time inside
# ``with app.app_context(): ...``. Point ``DB_PATH`` at a throwaway file
# before ``app`` is imported so importing this module never touches (or
# creates) the developer's real ``expense_tracker.db``. Each test then
# re-points DB_PATH at its own fresh temp file via the ``app`` fixture below,
# so no test shares state with another or with this bootstrap file.
_bootstrap_fd, _bootstrap_path = tempfile.mkstemp(suffix=".db")
os.close(_bootstrap_fd)
os.remove(_bootstrap_path)
db_module.DB_PATH = _bootstrap_path

from app import app as flask_app  # noqa: E402
from database.db import get_db, init_db  # noqa: E402
from database.queries import insert_expense  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def app(tmp_path, monkeypatch):
    """Point the app at a fresh, isolated SQLite file for every test."""
    db_path = tmp_path / "test_spendly.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    flask_app.config.update({"TESTING": True, "SECRET_KEY": "test-secret"})
    with flask_app.app_context():
        init_db()
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(name, email, password):
    """Insert a user directly via a parameterized query, using werkzeug's own
    hashing helper -- mirrors how /register stores credentials."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def _login(client, email, password):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False
    )


@pytest.fixture
def user_a(app):
    """A registered user with a known password, ready to log in."""
    user_id = _create_user("Alice Tester", "alice@example.com", "password123")
    return {"id": user_id, "email": "alice@example.com", "password": "password123"}


@pytest.fixture
def auth_client(client, user_a):
    """A test client that is already logged in as user_a via the real /login route."""
    resp = _login(client, user_a["email"], user_a["password"])
    assert resp.status_code == 302, "Login with valid credentials should redirect"
    return client


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _html(response):
    return response.data.decode("utf-8")


def _fetch_expenses(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    conn.close()
    return rows


VALID_PAYLOAD = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


def _payload(**overrides):
    data = dict(VALID_PAYLOAD)
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- #
# Unit tests -- database.queries.insert_expense
# --------------------------------------------------------------------------- #

class TestInsertExpenseHelper:
    def test_insert_expense_valid_row_is_persisted_and_queryable(self, app, user_a):
        insert_expense(user_a["id"], 50.0, "Food", "2026-03-20", "Lunch")

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 1, "insert_expense should create exactly one row"
        row = rows[0]
        assert row["user_id"] == user_a["id"]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_insert_expense_none_description_stored_as_null(self, app, user_a):
        insert_expense(user_a["id"], 12.5, "Transport", "2026-03-21", None)

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None, (
            "Passing description=None to insert_expense must store NULL, not "
            "an empty string or the literal text 'None'"
        )


# --------------------------------------------------------------------------- #
# GET /expenses/add
# --------------------------------------------------------------------------- #

class TestGetAddExpense:
    def test_get_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302, "Unauthenticated GET must redirect, not render the form"
        assert "/login" in resp.headers.get("Location", ""), "Must redirect to /login"

    def test_get_unauthenticated_does_not_touch_database(self, client, app):
        client.get("/expenses/add")
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        conn.close()
        assert count == 0

    def test_get_authenticated_returns_200(self, auth_client):
        resp = auth_client.get("/expenses/add")
        assert resp.status_code == 200

    def test_get_authenticated_form_has_post_method(self, auth_client):
        html = _html(auth_client.get("/expenses/add"))
        assert "<form" in html, "Expected an add-expense <form> in the response"
        assert 'method="POST"' in html, "Form must submit via POST"

    def test_get_authenticated_shows_all_required_fields(self, auth_client):
        html = _html(auth_client.get("/expenses/add"))
        assert 'name="amount"' in html
        assert 'name="category"' in html
        assert 'name="date"' in html
        assert 'name="description"' in html

    def test_get_authenticated_category_select_has_exactly_seven_fixed_options(self, auth_client):
        html = _html(auth_client.get("/expenses/add"))
        assert "<select" in html, "Category field must be a <select>"
        for category in CATEGORIES:
            assert f">{category}<" in html, f"Missing category option: {category}"

    def test_get_authenticated_date_field_defaults_to_today(self, auth_client):
        import datetime as dt

        today = dt.date.today().isoformat()
        html = _html(auth_client.get("/expenses/add"))
        assert today in html, "Date input should default to today's date when the form is first shown"

    def test_get_authenticated_has_cancel_link_back_to_profile(self, auth_client):
        html = _html(auth_client.get("/expenses/add"))
        assert "/profile" in html, "Expected a cancel link back to /profile"


# --------------------------------------------------------------------------- #
# POST /expenses/add -- auth guard
# --------------------------------------------------------------------------- #

class TestPostAuthGuard:
    def test_post_unauthenticated_redirects_to_login(self, client):
        resp = client.post("/expenses/add", data=_payload())
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")

    def test_post_unauthenticated_does_not_insert_anything(self, client, app):
        client.post("/expenses/add", data=_payload())
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        conn.close()
        assert count == 0, "Unauthenticated POST must never write to the database"


# --------------------------------------------------------------------------- #
# POST /expenses/add -- happy path
# --------------------------------------------------------------------------- #

class TestPostHappyPath:
    def test_post_valid_data_redirects_to_profile(self, auth_client):
        resp = auth_client.post("/expenses/add", data=_payload(), follow_redirects=False)
        assert resp.status_code == 302, "Successful submission should redirect, not re-render the form"
        assert resp.headers.get("Location", "").endswith("/profile"), (
            "Should redirect to the profile page, not somewhere else"
        )

    def test_post_valid_data_inserts_row_with_correct_values(self, auth_client, user_a):
        auth_client.post("/expenses/add", data=_payload())

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 1, "Exactly one expense row should be created"
        row = rows[0]
        assert row["user_id"] == user_a["id"]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_post_valid_data_then_appears_on_profile_page(self, auth_client):
        auth_client.post("/expenses/add", data=_payload(), follow_redirects=False)
        profile_html = _html(auth_client.get("/profile"))
        assert "Lunch" in profile_html, "Newly added expense should show up in the transaction list"

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_post_valid_data_accepts_each_of_the_seven_categories(self, auth_client, user_a, category):
        resp = auth_client.post("/expenses/add", data=_payload(category=category))
        assert resp.status_code == 302, f"Category {category!r} should be accepted"

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 1
        assert rows[0]["category"] == category


# --------------------------------------------------------------------------- #
# POST /expenses/add -- amount validation
# --------------------------------------------------------------------------- #

class TestAmountValidation:
    def test_post_missing_amount_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(amount=""))
        assert resp.status_code == 200, "Validation failure must re-render the form (200), not redirect"
        assert not _fetch_expenses(user_a["id"]), "No row should be inserted on validation failure"

    def test_post_zero_amount_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(amount="0"))
        assert resp.status_code == 200
        assert not _fetch_expenses(user_a["id"])

    def test_post_negative_amount_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(amount="-10"))
        assert resp.status_code == 200
        assert not _fetch_expenses(user_a["id"])

    def test_post_non_numeric_amount_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(amount="abc"))
        assert resp.status_code == 200
        assert not _fetch_expenses(user_a["id"])

    def test_post_missing_amount_shows_error_message_and_repopulates_other_fields(
        self, auth_client
    ):
        html = _html(auth_client.post("/expenses/add", data=_payload(amount="", description="Coffee")))
        assert "auth-error" in html or "error" in html.lower(), (
            "Expected an error message to be displayed when amount is missing"
        )
        assert "Coffee" in html, (
            "Previously submitted description should be retained/re-populated on validation error"
        )

    def test_post_invalid_amount_does_not_crash_with_server_error(self, auth_client):
        resp = auth_client.post("/expenses/add", data=_payload(amount="not-a-number"))
        assert resp.status_code != 500, "Invalid amount must be handled gracefully, never a 500"


# --------------------------------------------------------------------------- #
# POST /expenses/add -- category validation
# --------------------------------------------------------------------------- #

class TestCategoryValidation:
    def test_post_invalid_category_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(category="NotACategory"))
        assert resp.status_code == 200
        assert not _fetch_expenses(user_a["id"])

    def test_post_missing_category_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(category=""))
        assert resp.status_code == 200
        assert not _fetch_expenses(user_a["id"])

    def test_post_invalid_category_shows_error_message(self, auth_client):
        html = _html(auth_client.post("/expenses/add", data=_payload(category="Rent")))
        assert "auth-error" in html or "error" in html.lower()


# --------------------------------------------------------------------------- #
# POST /expenses/add -- date validation
# --------------------------------------------------------------------------- #

class TestDateValidation:
    def test_post_invalid_date_string_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(date="not-a-date"))
        assert resp.status_code == 200
        assert not _fetch_expenses(user_a["id"])

    def test_post_missing_date_rerenders_form_with_error(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(date=""))
        assert resp.status_code == 200
        assert not _fetch_expenses(user_a["id"])

    @pytest.mark.parametrize(
        "bad_date",
        ["31-12-2026", "2026/03/20", "2026-13-40", "not-a-date", "20-03-2026"],
    )
    def test_post_malformed_date_formats_rerender_form_with_error(self, auth_client, user_a, bad_date):
        resp = auth_client.post("/expenses/add", data=_payload(date=bad_date))
        assert resp.status_code == 200, f"Date {bad_date!r} should be rejected, re-rendering the form"
        assert not _fetch_expenses(user_a["id"])

    def test_post_invalid_date_shows_error_message(self, auth_client):
        html = _html(auth_client.post("/expenses/add", data=_payload(date="not-a-date")))
        assert "auth-error" in html or "error" in html.lower()


# --------------------------------------------------------------------------- #
# POST /expenses/add -- description handling (optional field)
# --------------------------------------------------------------------------- #

class TestDescriptionHandling:
    def test_post_empty_description_saves_expense_with_null_description(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(description=""))
        assert resp.status_code == 302, "Missing description must not be treated as a validation error"
        assert resp.headers.get("Location", "").endswith("/profile")

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_post_whitespace_only_description_saves_as_null(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(description="   "))
        assert resp.status_code == 302

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None, (
            "A description containing only whitespace should be stripped and stored as NULL"
        )

    def test_post_description_is_stripped_of_surrounding_whitespace(self, auth_client, user_a):
        auth_client.post("/expenses/add", data=_payload(description="  Groceries  "))

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 1
        assert rows[0]["description"] == "Groceries"

    def test_post_description_provided_is_persisted_as_is(self, auth_client, user_a):
        auth_client.post("/expenses/add", data=_payload(description="Team lunch at cafe"))

        rows = _fetch_expenses(user_a["id"])
        assert rows[0]["description"] == "Team lunch at cafe"


# --------------------------------------------------------------------------- #
# DB side effects -- scoping / cross-user isolation
# --------------------------------------------------------------------------- #

class TestDatabaseSideEffectsAndScoping:
    def test_post_valid_data_scopes_new_expense_to_logged_in_user(self, auth_client, user_a):
        other_user_id = _create_user("Bob Tester", "bob@example.com", "password456")

        auth_client.post("/expenses/add", data=_payload(description="Mine"))

        own_rows = _fetch_expenses(user_a["id"])
        other_rows = _fetch_expenses(other_user_id)
        assert len(own_rows) == 1, "The expense should be attributed to the logged-in user"
        assert own_rows[0]["description"] == "Mine"
        assert len(other_rows) == 0, "No expense should leak to another user's account"

    def test_post_validation_failure_never_creates_a_row_for_any_user(self, auth_client, user_a):
        other_user_id = _create_user("Bob Tester", "bob@example.com", "password456")

        auth_client.post("/expenses/add", data=_payload(amount="0"))

        assert len(_fetch_expenses(user_a["id"])) == 0
        assert len(_fetch_expenses(other_user_id)) == 0

    def test_multiple_valid_submissions_each_create_their_own_row(self, auth_client, user_a):
        auth_client.post("/expenses/add", data=_payload(description="First"))
        auth_client.post("/expenses/add", data=_payload(description="Second"))

        rows = _fetch_expenses(user_a["id"])
        assert len(rows) == 2
        descriptions = {row["description"] for row in rows}
        assert descriptions == {"First", "Second"}


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #

class TestEdgeCases:
    def test_post_very_long_description_within_max_length_is_accepted(self, auth_client, user_a):
        long_description = "x" * 200  # spec's stated max length
        resp = auth_client.post("/expenses/add", data=_payload(description=long_description))
        assert resp.status_code == 302

        rows = _fetch_expenses(user_a["id"])
        assert rows[0]["description"] == long_description

    def test_post_sql_injection_attempt_in_description_is_stored_safely_as_literal_text(
        self, auth_client, user_a
    ):
        malicious = "Lunch'); DROP TABLE expenses;--"
        resp = auth_client.post("/expenses/add", data=_payload(description=malicious))
        assert resp.status_code == 302, "The request should be handled normally, not error out"

        # The expenses table must still exist and contain the literal string,
        # proving the value was never concatenated into a SQL statement.
        conn = get_db()
        row = conn.execute(
            "SELECT description FROM expenses WHERE user_id = ?", (user_a["id"],)
        ).fetchone()
        conn.close()
        assert row is not None, "Expenses table should be unaffected by the injection attempt"
        assert row["description"] == malicious

    def test_post_sql_injection_attempt_in_category_is_rejected_as_invalid_category(
        self, auth_client, user_a
    ):
        resp = auth_client.post(
            "/expenses/add", data=_payload(category="Food'; DROP TABLE expenses;--")
        )
        assert resp.status_code == 200, "Unrecognized category strings must fail validation, not be inserted"
        assert not _fetch_expenses(user_a["id"])

    def test_post_amount_with_many_decimal_places_is_accepted_as_a_float(self, auth_client, user_a):
        resp = auth_client.post("/expenses/add", data=_payload(amount="19.999"))
        assert resp.status_code == 302
        rows = _fetch_expenses(user_a["id"])
        assert rows[0]["amount"] == pytest.approx(19.999)


# --------------------------------------------------------------------------- #
# Navigation landmarks (DoD: Add Expense entry points)
# --------------------------------------------------------------------------- #

class TestNavigationLandmarks:
    def test_profile_page_has_add_expense_link(self, auth_client):
        html = _html(auth_client.get("/profile"))
        assert "/expenses/add" in html, "Profile page should link to the Add Expense form"

    def test_navbar_shows_add_expense_link_when_logged_in(self, auth_client):
        html = _html(auth_client.get("/profile"))
        assert "Add Expense" in html

    def test_navbar_hides_add_expense_link_when_logged_out(self, client):
        html = _html(client.get("/"))
        assert "/expenses/add" not in html, (
            "Add Expense link should not be shown in the navbar to logged-out visitors"
        )
