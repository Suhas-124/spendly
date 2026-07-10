"""
Tests for the Spendly "Date Filter" feature (Step 6).

Spec: .claude/specs/06-date-filter.md
`GET /profile` gains optional `range` / `start_date` / `end_date` query-string
parameters that narrow the stats, transactions, and category breakdown to a
time window, defaulting to "all time" behavior identical to Step 5 when no
filter is supplied.

These tests are written strictly from the spec's described behavior. `app.py`
and `database/db.py` were only consulted for structural conventions (route
paths, the `login_required` pattern, the `users`/`expenses` schema, and
`get_db()`'s `DB_PATH` resolution) so that fixtures can log in through the
real `/login` route and seed known data — not to derive filtering logic.
"""

import os
import re
import tempfile
from datetime import date, timedelta

import pytest

import database.db as db_module

# ``app.py`` runs ``init_db()`` / ``seed_db()`` at *import* time (inside
# ``with app.app_context(): ...``). To make sure importing this test module
# never touches the developer's real ``expense_tracker.db``, we redirect
# ``database.db.DB_PATH`` to a throwaway file *before* ``app`` is imported.
# Each test then re-points DB_PATH at its own fresh temp file via the
# ``app`` fixture below, so tests never share state.
_bootstrap_fd, _bootstrap_path = tempfile.mkstemp(suffix=".db")
os.close(_bootstrap_fd)
os.remove(_bootstrap_path)
db_module.DB_PATH = _bootstrap_path

from app import app as flask_app  # noqa: E402
from database.db import get_db, init_db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


# --------------------------------------------------------------------------- #
# Date helpers — mirror the plain-language range definitions from the spec,
# not any implementation, so expected boundaries can be computed independently.
# --------------------------------------------------------------------------- #

_TODAY = date.today()


def _iso(d):
    return d.isoformat()


def _this_month_bounds():
    """'first day of current month through today'"""
    return _TODAY.replace(day=1), _TODAY


def _last_month_bounds():
    """'first through last day of the previous calendar month'"""
    first_this_month = _TODAY.replace(day=1)
    last_day_prev_month = first_this_month - timedelta(days=1)
    first_day_prev_month = last_day_prev_month.replace(day=1)
    return first_day_prev_month, last_day_prev_month


def _last_30_bounds():
    """'today minus 29 days through today'"""
    return _TODAY - timedelta(days=29), _TODAY


_TOMORROW_SAME_MONTH = (_TODAY + timedelta(days=1)).month == _TODAY.month


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
    hashing helper — mirrors how /register stores credentials."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def _insert_expense(user_id, amount, category, expense_date, description="Test expense"):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


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
    """A test client logged in as user_a via the real /login route."""
    resp = _login(client, user_a["email"], user_a["password"])
    assert resp.status_code == 302, "Login with valid credentials should redirect"
    return client


# --------------------------------------------------------------------------- #
# HTML assertion helpers (based on templates/profile.html structure)
# --------------------------------------------------------------------------- #

def _html(response):
    return response.data.decode("utf-8")


def _extract_stat(html, label):
    """Pull the text of a `.stat-value` given its preceding `.stat-label`."""
    pattern = rf'{re.escape(label)}</span>\s*<span class="stat-value">(.*?)</span>'
    match = re.search(pattern, html)
    assert match, f"Could not find stat labeled {label!r} in response HTML"
    return match.group(1).strip()


def _total_spent(html):
    return _extract_stat(html, "Total Spent")


def _transaction_count(html):
    return _extract_stat(html, "Transactions")


def _top_category(html):
    return _extract_stat(html, "Top Category")


def _filter_error_message(html):
    match = re.search(r'<div class="auth-error">(.*?)</div>', html)
    return match.group(1).strip() if match else None


def _selected_range_option(html):
    match = re.search(r'<option value="(\w+)" selected>', html)
    return match.group(1) if match else None


def _filter_dates_hidden(html):
    match = re.search(r'id="filter-dates" class="([^"]*)"', html)
    assert match, "Could not find the #filter-dates container in response HTML"
    return "is-hidden" in match.group(1).split()


def _date_input_value(html, field_name):
    match = re.search(rf'name="{field_name}"[^>]*value="([^"]*)"', html)
    assert match, f"Could not find date input {field_name!r} in response HTML"
    return match.group(1)


def money(amount):
    return f"{amount:.2f}"


# --------------------------------------------------------------------------- #
# 10. Auth guard
# --------------------------------------------------------------------------- #

class TestAuthGuard:
    def test_profile_no_params_requires_login_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302, "Unauthenticated /profile should redirect"
        assert "/login" in resp.headers.get("Location", ""), "Should redirect to /login"

    @pytest.mark.parametrize(
        "query_string",
        [
            {"range": "this_month"},
            {"range": "last_month"},
            {"range": "last_30"},
            {"range": "custom", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        ],
    )
    def test_profile_with_filter_params_requires_login_redirects_to_login(
        self, client, query_string
    ):
        resp = client.get("/profile", query_string=query_string)
        assert resp.status_code == 302, (
            "Unauthenticated /profile with filter params should still redirect, "
            f"got {resp.status_code} for params={query_string}"
        )
        assert "/login" in resp.headers.get("Location", "")


# --------------------------------------------------------------------------- #
# 1. GET /profile with no query params == pre-existing all-time behavior
# --------------------------------------------------------------------------- #

class TestAllTimeRegression:
    def test_profile_no_query_params_returns_all_time_stats(self, auth_client, user_a):
        _insert_expense(user_a["id"], 10.00, "Food", _iso(_TODAY - timedelta(days=400)), "Very old")
        _insert_expense(user_a["id"], 20.00, "Transport", _iso(_TODAY - timedelta(days=40)), "Old")
        _insert_expense(user_a["id"], 30.00, "Bills", _iso(_TODAY), "Recent")

        resp = auth_client.get("/profile")
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(60.00)}", "All-time total should sum every expense"
        assert _transaction_count(html) == "3"
        assert "Very old" in html
        assert "Old" in html
        assert "Recent" in html
        assert _filter_error_message(html) is None, "No filter_error expected for the default view"

    def test_profile_explicit_range_all_matches_no_params(self, auth_client, user_a):
        _insert_expense(user_a["id"], 15.00, "Food", _iso(_TODAY - timedelta(days=100)), "A")
        _insert_expense(user_a["id"], 25.00, "Food", _iso(_TODAY), "B")

        resp_default = auth_client.get("/profile")
        resp_explicit = auth_client.get("/profile", query_string={"range": "all"})

        assert resp_default.status_code == 200
        assert resp_explicit.status_code == 200
        html_default = _html(resp_default)
        html_explicit = _html(resp_explicit)

        assert _total_spent(html_default) == _total_spent(html_explicit)
        assert _transaction_count(html_default) == _transaction_count(html_explicit)


# --------------------------------------------------------------------------- #
# 2. this_month
# --------------------------------------------------------------------------- #

class TestThisMonth:
    def test_profile_this_month_filters_to_current_calendar_month(self, auth_client, user_a):
        start, end = _this_month_bounds()

        _insert_expense(user_a["id"], 50.00, "Food", _iso(start), "InMonthStart")
        _insert_expense(user_a["id"], 20.00, "Food", _iso(end), "InMonthToday")
        # Definitely outside this month: one full month before the window start.
        outside_date = start - timedelta(days=1)
        _insert_expense(user_a["id"], 999.00, "Bills", _iso(outside_date), "OutsideMonth")

        resp = auth_client.get("/profile", query_string={"range": "this_month"})
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(70.00)}"
        assert _transaction_count(html) == "2"
        assert "InMonthStart" in html
        assert "InMonthToday" in html
        assert "OutsideMonth" not in html
        assert _filter_error_message(html) is None

    @pytest.mark.skipif(
        not _TOMORROW_SAME_MONTH,
        reason="Today is the last day of the month; no future date exists within "
        "the current month to exercise the upper bound.",
    )
    def test_profile_this_month_excludes_dates_after_today(self, auth_client, user_a):
        _, end = _this_month_bounds()
        future_in_month = end + timedelta(days=1)

        _insert_expense(user_a["id"], 10.00, "Food", _iso(end), "TodayExpense")
        _insert_expense(user_a["id"], 500.00, "Bills", _iso(future_in_month), "FutureThisMonth")

        resp = auth_client.get("/profile", query_string={"range": "this_month"})
        html = _html(resp)

        assert "TodayExpense" in html
        assert "FutureThisMonth" not in html, (
            "'this_month' upper bound is today, not month-end, so future dates "
            "within the same month must be excluded"
        )
        assert _total_spent(html) == f"₹{money(10.00)}"


# --------------------------------------------------------------------------- #
# 3. last_month
# --------------------------------------------------------------------------- #

class TestLastMonth:
    def test_profile_last_month_filters_to_previous_calendar_month(self, auth_client, user_a):
        first_prev, last_prev = _last_month_bounds()

        _insert_expense(user_a["id"], 40.00, "Food", _iso(first_prev), "PrevMonthStart")
        _insert_expense(user_a["id"], 60.00, "Transport", _iso(last_prev), "PrevMonthEnd")
        _insert_expense(
            user_a["id"], 500.00, "Bills", _iso(last_prev + timedelta(days=1)), "ThisMonthExcluded"
        )
        _insert_expense(
            user_a["id"], 500.00, "Bills", _iso(first_prev - timedelta(days=1)), "TwoMonthsAgoExcluded"
        )

        resp = auth_client.get("/profile", query_string={"range": "last_month"})
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(100.00)}"
        assert _transaction_count(html) == "2"
        assert "PrevMonthStart" in html
        assert "PrevMonthEnd" in html
        assert "ThisMonthExcluded" not in html
        assert "TwoMonthsAgoExcluded" not in html


# --------------------------------------------------------------------------- #
# 4. last_30
# --------------------------------------------------------------------------- #

class TestLast30Days:
    def test_profile_last_30_filters_to_last_30_days_inclusive(self, auth_client, user_a):
        start, end = _last_30_bounds()

        _insert_expense(user_a["id"], 12.00, "Food", _iso(start), "ExactlyOldestIncluded")
        _insert_expense(user_a["id"], 8.00, "Food", _iso(end), "TodayIncluded")
        _insert_expense(
            user_a["id"], 999.00, "Bills", _iso(start - timedelta(days=1)), "Day30AgoExcluded"
        )

        resp = auth_client.get("/profile", query_string={"range": "last_30"})
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(20.00)}"
        assert _transaction_count(html) == "2"
        assert "ExactlyOldestIncluded" in html
        assert "TodayIncluded" in html
        assert "Day30AgoExcluded" not in html


# --------------------------------------------------------------------------- #
# 5. custom (valid)
# --------------------------------------------------------------------------- #

class TestCustomRangeValid:
    def test_profile_custom_valid_range_filters_inclusive_bounds(self, auth_client, user_a):
        start = _TODAY - timedelta(days=10)
        end = _TODAY - timedelta(days=5)

        _insert_expense(user_a["id"], 5.00, "Food", _iso(start), "CustomStartIncluded")
        _insert_expense(user_a["id"], 7.00, "Food", _iso(start + timedelta(days=2)), "CustomMidIncluded")
        _insert_expense(user_a["id"], 9.00, "Food", _iso(end), "CustomEndIncluded")
        _insert_expense(
            user_a["id"], 999.00, "Bills", _iso(start - timedelta(days=1)), "BeforeCustomExcluded"
        )
        _insert_expense(
            user_a["id"], 999.00, "Bills", _iso(end + timedelta(days=1)), "AfterCustomExcluded"
        )

        resp = auth_client.get(
            "/profile",
            query_string={"range": "custom", "start_date": _iso(start), "end_date": _iso(end)},
        )
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(21.00)}"
        assert _transaction_count(html) == "3"
        assert "CustomStartIncluded" in html
        assert "CustomMidIncluded" in html
        assert "CustomEndIncluded" in html
        assert "BeforeCustomExcluded" not in html
        assert "AfterCustomExcluded" not in html
        assert _filter_error_message(html) is None


# --------------------------------------------------------------------------- #
# 6. custom (invalid / missing) — must degrade to all-time, never 500
# --------------------------------------------------------------------------- #

class TestCustomRangeInvalid:
    @pytest.fixture(autouse=True)
    def _seed_all_time_data(self, auth_client, user_a):
        """Fixture data whose all-time total is used to assert fallback behavior."""
        _insert_expense(user_a["id"], 11.00, "Food", _iso(_TODAY - timedelta(days=200)), "AllTimeA")
        _insert_expense(user_a["id"], 22.00, "Transport", _iso(_TODAY), "AllTimeB")
        self.expected_total = 33.00
        self.expected_count = "2"

    @pytest.mark.parametrize(
        "extra_params",
        [
            pytest.param({}, id="both_dates_omitted"),
            pytest.param({"start_date": "", "end_date": ""}, id="both_dates_empty_string"),
            pytest.param({"end_date": lambda: _iso(_TODAY)}, id="start_date_missing"),
            pytest.param({"start_date": lambda: _iso(_TODAY)}, id="end_date_missing"),
            pytest.param(
                {"start_date": "not-a-date", "end_date": lambda: _iso(_TODAY)},
                id="start_date_invalid_format",
            ),
            pytest.param(
                {"start_date": lambda: _iso(_TODAY - timedelta(days=5)), "end_date": "31-12-2026"},
                id="end_date_invalid_format",
            ),
            pytest.param(
                {
                    "start_date": lambda: _iso(_TODAY),
                    "end_date": lambda: _iso(_TODAY - timedelta(days=5)),
                },
                id="start_after_end",
            ),
        ],
    )
    def test_profile_custom_invalid_or_missing_dates_falls_back_to_all(
        self, auth_client, extra_params
    ):
        params = {"range": "custom"}
        for key, value in extra_params.items():
            params[key] = value() if callable(value) else value

        resp = auth_client.get("/profile", query_string=params)

        assert resp.status_code != 500, "Invalid custom range must never raise a server error"
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(self.expected_total)}", (
            "Invalid/missing custom dates should fall back to all-time totals"
        )
        assert _transaction_count(html) == self.expected_count
        assert _filter_error_message(html) is not None, (
            "A validation message should be shown when the custom range is invalid"
        )


# --------------------------------------------------------------------------- #
# 7. Unrecognized range value degrades gracefully to "all"
# --------------------------------------------------------------------------- #

class TestUnrecognizedRange:
    def test_profile_unrecognized_range_value_degrades_to_all(self, auth_client, user_a):
        _insert_expense(user_a["id"], 14.00, "Food", _iso(_TODAY - timedelta(days=300)), "Old")
        _insert_expense(user_a["id"], 16.00, "Food", _iso(_TODAY), "Recent")

        resp = auth_client.get("/profile", query_string={"range": "not_a_real_range"})
        assert resp.status_code != 500
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(30.00)}"
        assert _transaction_count(html) == "2"
        assert "Old" in html
        assert "Recent" in html


# --------------------------------------------------------------------------- #
# 8. Zero results in range
# --------------------------------------------------------------------------- #

class TestZeroResults:
    def test_profile_zero_expenses_total_returns_empty_stats(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(0.0)}"
        assert _transaction_count(html) == "0"
        assert _top_category(html) == "—"

    def test_profile_expenses_exist_but_none_in_range_returns_empty_stats(
        self, auth_client, user_a
    ):
        # All expenses are far in the past; filtering to "this_month" should
        # yield zero/empty stats without erroring, even though the user has
        # expenses overall.
        _insert_expense(user_a["id"], 100.00, "Food", _iso(_TODAY - timedelta(days=500)), "Ancient")

        resp = auth_client.get("/profile", query_string={"range": "this_month"})
        assert resp.status_code == 200
        html = _html(resp)

        assert _total_spent(html) == f"₹{money(0.0)}"
        assert _transaction_count(html) == "0"
        assert _top_category(html) == "—"
        assert "Ancient" not in html


# --------------------------------------------------------------------------- #
# 9. Cross-user isolation
# --------------------------------------------------------------------------- #

class TestCrossUserIsolation:
    def test_profile_cross_user_expenses_never_leak_into_filtered_results(
        self, auth_client, user_a
    ):
        user_b_id = _create_user("Bob Tester", "bob@example.com", "password456")

        # Same dates for both users so any leakage would be caught by any range.
        _insert_expense(user_a["id"], 10.00, "Food", _iso(_TODAY), "AliceExpense")
        _insert_expense(user_b_id, 999.00, "Bills", _iso(_TODAY), "BobExpense")

        for query in (
            {},
            {"range": "this_month"},
            {"range": "last_30"},
            {
                "range": "custom",
                "start_date": _iso(_TODAY - timedelta(days=1)),
                "end_date": _iso(_TODAY),
            },
        ):
            resp = auth_client.get("/profile", query_string=query)
            html = _html(resp)

            assert "BobExpense" not in html, f"Leaked Bob's expense for query={query}"
            assert "AliceExpense" in html, f"Missing Alice's own expense for query={query}"
            assert _total_spent(html) == f"₹{money(10.00)}", (
                f"Total should only include Alice's expense for query={query}"
            )
            assert _transaction_count(html) == "1"


# --------------------------------------------------------------------------- #
# 11. Transactions stay capped at 5 within a filtered window
# --------------------------------------------------------------------------- #

class TestTransactionCap:
    def test_profile_transactions_capped_at_five_within_filtered_range(
        self, auth_client, user_a
    ):
        # 7 distinct days, all inside the last-30-day window, guaranteed room
        # regardless of what day of the month "today" is.
        labels = []
        for days_ago in range(7):
            label = f"Day{days_ago}Ago"
            labels.append(label)
            _insert_expense(
                user_a["id"], 1.00 + days_ago, "Food", _iso(_TODAY - timedelta(days=days_ago)), label
            )

        resp = auth_client.get("/profile", query_string={"range": "last_30"})
        assert resp.status_code == 200
        html = _html(resp)

        # Stats reflect ALL 7 in-range expenses (cap only applies to the table).
        assert _transaction_count(html) == "7"

        # But only 5 transaction rows are rendered.
        badge_count = html.count('class="category-badge"')
        assert badge_count == 5, f"Expected 5 transaction rows, found {badge_count}"

        # The 5 most recent (today down to 4 days ago) should be shown...
        for label in labels[:5]:
            assert label in html, f"Expected most-recent expense {label!r} to be shown"

        # ...and the 2 oldest should be excluded from the capped table.
        for label in labels[5:]:
            assert label not in html, f"Did not expect older expense {label!r} in capped table"


# --------------------------------------------------------------------------- #
# Filter form reflects the current request's query params (DoD requirement)
# --------------------------------------------------------------------------- #

class TestFilterFormState:
    def test_profile_filter_form_reflects_this_month_selection(self, auth_client):
        resp = auth_client.get("/profile", query_string={"range": "this_month"})
        html = _html(resp)

        assert _selected_range_option(html) == "this_month"
        assert _filter_dates_hidden(html) is True, (
            "Custom date inputs should stay visually hidden for non-custom presets"
        )

    def test_profile_filter_form_reflects_custom_selection_and_dates(self, auth_client):
        start = _iso(_TODAY - timedelta(days=7))
        end = _iso(_TODAY)

        resp = auth_client.get(
            "/profile",
            query_string={"range": "custom", "start_date": start, "end_date": end},
        )
        html = _html(resp)

        assert _selected_range_option(html) == "custom"
        assert _filter_dates_hidden(html) is False, (
            "Custom date inputs should be visible when 'custom' is selected"
        )
        assert _date_input_value(html, "start_date") == start
        assert _date_input_value(html, "end_date") == end

    def test_profile_filter_form_defaults_to_all_with_no_params(self, auth_client):
        resp = auth_client.get("/profile")
        html = _html(resp)

        assert _selected_range_option(html) == "all"
        assert _filter_dates_hidden(html) is True
