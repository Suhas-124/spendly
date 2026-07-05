---
# Spec: Registration

## Overview
This step implements real account creation for Spendly. The `/register` route currently only renders `register.html` on GET with no server-side logic. Building on the SQLite data layer from Step 1 (`database/db.py`), this step wires up the `POST /register` handler so visitors can create a real, persisted account: validating form input, rejecting duplicate emails, hashing passwords with werkzeug, and inserting a new row into the `users` table. Session creation / auto-login is intentionally out of scope — that belongs with the login step, since `logout` (Step 3) and `profile` (Step 4) are the first stubs that require an active session.

## Depends on
- Step 1 (Database Setup) — requires `database/db.py`'s `get_db()` and `init_db()` to be working, and the `users` table (`id`, `name`, `email` UNIQUE, `password_hash`, `created_at`) to exist.

## Routes
- `GET /register` — render empty registration form — public (already exists, unchanged)
- `POST /register` — validate submitted form, create account, redirect to `/login` on success or re-render form with an error on failure — public

## Database changes
No database changes. The `users` table already has the columns needed (`name`, `email`, `password_hash`).

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — no structural changes required; it already posts to `/register` and has an `{% if error %}` block. The route will pass `error` (and optionally re-populate submitted `name`/`email` values) on validation failure.

## Files to change
- `app.py` — change `/register` route to accept `methods=["GET", "POST"]`; on POST, validate input, check for duplicate email, hash the password, insert the new user via `database/db.py`'s `get_db()`, then redirect to `/login`.

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`) — never store or log plaintext passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate server-side even though HTML5 `required`/`type=email` attributes exist client-side: reject empty `name`/`email`/`password`
- Enforce a minimum password length of 8 characters (matches the placeholder text already in `register.html`)
- On duplicate email (`UNIQUE` constraint / pre-check), re-render `register.html` with a clear error (e.g. "An account with this email already exists.") — no partial/duplicate row written
- On success, redirect with `redirect(url_for("login"))` — do not create a session or log the user in as part of this step
- Reuse `get_db()` from `database/db.py` for the insert; do not open a raw `sqlite3.connect()` in `app.py`

## Definition of done
- [ ] `GET /register` still renders the empty form with no errors
- [ ] Submitting valid name/email/password creates a new row in the `users` table with a werkzeug-hashed `password_hash` (not plaintext)
- [ ] Submitting an email that already exists in `users` re-renders `register.html` with an error message and does not create a duplicate row
- [ ] Submitting with a missing `name`, `email`, or `password` re-renders the form with a validation error and does not create a row
- [ ] Submitting a password shorter than 8 characters re-renders the form with a validation error and does not create a row
- [ ] Successful registration redirects to `/login`
- [ ] App starts and runs (`python app.py`) without errors after the change
