---
# Spec: Login and Logout

## Overview
This step wires up real session-based authentication for Spendly. `GET /login` already renders `login.html` with a working form, but the route has no `POST` handler, and `/logout` is a placeholder that just returns a string. Building on Step 1 (database layer) and Step 2 (registration), this step verifies submitted credentials against the `users` table, establishes a logged-in session on success, and tears that session down on logout. It also makes the navbar in `base.html` reflect whether a visitor is signed in, since that's the only user-visible signal that login/logout actually did anything before Step 4 (Profile) exists. Protecting routes like `/profile` or `/expenses/*` with a login-required guard is explicitly out of scope — that belongs to the steps that build those features (Steps 4, 7, 8, 9).

## Depends on
- Step 1 (Database Setup) — requires `database/db.py`'s `get_db()` and the `users` table (`id`, `name`, `email`, `password_hash`) to exist.
- Step 2 (Registration) — requires `POST /register` to be able to create a real user with a werkzeug-hashed password to log in with.

## Routes
- `GET /login` — render empty login form — public (already exists, unchanged)
- `POST /login` — validate submitted email/password against `users`, start a session on success, re-render form with an error on failure — public
- `GET /logout` — clear the session and redirect to the landing page — logged-in (redirect harmlessly to `/` if already logged out, no error needed)

## Database changes
No database changes. The `users` table already has the columns needed (`id`, `name`, `email`, `password_hash`).

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — no structural changes required; it already posts to `/login` and has an `{% if error %}` block. The route will pass `error` (and optionally re-populate the submitted `email`) on validation failure.
  - `templates/base.html` — navbar (`.nav-links`, around lines 21-24) currently always shows "Sign in" / "Get started". Change it to check `session.get('user_id')`: if logged in, show the user's name (or "Profile") linking to `url_for('profile')` and a "Logout" link to `url_for('logout')`; if logged out, keep the existing "Sign in" / "Get started" links unchanged.

## Files to change
- `app.py`:
  - Set `app.secret_key` so Flask sessions work (read from an environment variable with a hardcoded local-dev fallback, since there's no config/env-loading system in this project yet).
  - Change `/login` route to accept `methods=["GET", "POST"]`; on `POST`, look up the user by email, verify the password with `check_password_hash`, and on success store `session['user_id']` and `session['user_name']`, then redirect to `/profile`. On failure (no such email, or wrong password), re-render `login.html` with a single generic error (don't reveal whether the email exists).
  - Change `/logout` route to pop the session (`session.clear()`) and redirect to `/` (landing page), replacing the current `"Logout — coming in Step 3"` placeholder string.
- `templates/base.html` — add the session-aware navbar conditional described above.

## Files to create
None.

## New dependencies
No new dependencies. Uses Flask's built-in `session` and `werkzeug.security.check_password_hash` (`generate_password_hash` is already imported for registration).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`, never compare plaintext passwords directly
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate server-side even though HTML5 `required`/`type=email` attributes exist client-side: reject empty `email`/`password` on `POST /login`
- Use one generic error message ("Invalid email or password.") for both "no such user" and "wrong password" cases — don't leak which one it was
- Reuse `get_db()` from `database/db.py` for the lookup; do not open a raw `sqlite3.connect()` in `app.py`
- Do not implement a `login_required` decorator or guard `/profile`/`/expenses/*` routes in this step — that's Step 4/7/8/9 scope
- Do not store password hashes or plaintext passwords in the session — only `user_id` (and optionally `user_name` for display)

## Definition of done
- [ ] `GET /login` still renders the empty form with no errors
- [ ] Submitting a registered user's correct email/password logs them in (session cookie set) and redirects to `/profile`
- [ ] Submitting a correct email with the wrong password re-renders `login.html` with "Invalid email or password." and does not start a session
- [ ] Submitting an email that doesn't exist re-renders `login.html` with the same generic error and does not start a session
- [ ] Submitting with a missing `email` or `password` re-renders the form with a validation error
- [ ] After logging in, the navbar shows the logged-in state (name/profile link + logout) instead of "Sign in" / "Get started"
- [ ] Visiting `/logout` while logged in clears the session, redirects to `/`, and the navbar reverts to the logged-out state
- [ ] Visiting `/logout` while already logged out does not error and redirects to `/`
- [ ] App starts and runs (`python app.py`) without errors after the change
