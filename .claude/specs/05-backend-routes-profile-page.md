---
# Spec: Backend Routes for Profile Page

## Overview
This step replaces the hardcoded Python dicts/lists in the `/profile` view with real queries against the `users` and `expenses` tables. Step 4 deliberately built the profile UI first with static data so the template and layout could be validated in isolation; now that the data layer (Step 1) and a logged-in session with a real `user_id` (Steps 2–3) both exist, `/profile` can compute the user info card, summary stats, transaction history, and category breakdown from actual rows scoped to the logged-in user. No new routes or templates are introduced — this is a pure backend wiring step.

## Depends on
- Step 1 (Database Setup) — requires `database/db.py`'s `get_db()` and the `users` (`id`, `name`, `email`, `created_at`) and `expenses` (`user_id`, `amount`, `category`, `date`, `description`) tables.
- Step 2 (Registration) — requires real user rows to exist.
- Step 3 (Login and Logout) — requires `session['user_id']` to be set for the logged-in user.
- Step 4 (Profile Page Creation) — requires `templates/profile.html` and the `login_required` guard on `/profile` already in place; this step keeps that template's variable contract unchanged (`user`, `stats`, `transactions`, `categories`).

## Routes
No new routes. `GET /profile` — unchanged signature (still logged-in only, redirects to `/login` if `session.get('user_id')` is absent) — but its body now derives all context from the database instead of hardcoded values.

## Database changes
No database changes. The existing `users` and `expenses` tables are sufficient for every value the template needs.

## Templates
- **Create:** none
- **Modify:** none. `templates/profile.html` already consumes `user`, `stats`, `transactions`, `categories` exactly as structured today — only the Python values feeding those variables change, not the template.

## Files to change
- `app.py` — rewrite the `/profile` view function:
  - Look up the logged-in user by `session['user_id']` via `get_db()` (`SELECT id, name, email, created_at FROM users WHERE id = ?`) instead of trusting `session['user_name']`/`session['user_email']` alone, so the profile always reflects the current DB row.
  - Compute `user.initials` from the DB `name` the same way as today (first letter of up to the first two words, uppercased).
  - Compute `user.member_since` by parsing the `created_at` TEXT column (`datetime('now')` format, e.g. `"2026-07-07 10:23:45"`) into a `"Month YYYY"` display string (e.g. `"July 2026"`).
  - Query all `expenses` rows for `user_id` to compute:
    - `stats.total_spent` — `SUM(amount)` for the user (`0.0` if no expenses)
    - `stats.transaction_count` — `COUNT(*)` for the user
    - `stats.top_category` — the `category` with the highest summed `amount` for the user (`None`/`"—"` if no expenses)
  - Query the user's expenses ordered by `date DESC` (limit to the 5 most recent, matching the current template's row count) for `transactions`, reformatting each row's `date` from the stored `YYYY-MM-DD` format to the template's existing `DD-MM-YYYY` display format.
  - Query per-category totals for the user (`GROUP BY category`) for `categories`, each with `name`, `total`, and `percent` (`round(total / stats.total_spent * 100)`, `0` if `total_spent` is `0`), sorted by `total` descending to match the current display order.

## Files to create
None.

## New dependencies
No new dependencies. Use Python's built-in `datetime` module (already available via the standard library) to parse `created_at` and reformat transaction dates.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL, always filter by `user_id = ?`
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Reuse `get_db()` from `database/db.py` for every query; do not open a raw `sqlite3.connect()` in `app.py`
- Every expense query must be scoped to the logged-in `user_id` — never return another user's expenses
- Keep the exact same context variable names/shapes (`user`, `stats`, `transactions`, `categories`) that `templates/profile.html` already expects, so the template requires no changes
- Handle the zero-expenses case gracefully (new user with no data yet): `total_spent` is `0.0`, `transaction_count` is `0`, `top_category` and the transaction/category lists are empty without raising an error

## Definition of done
- [ ] Visiting `/profile` without being logged in still redirects to `/login`
- [ ] Visiting `/profile` while logged in returns HTTP 200 and renders with no template errors
- [ ] The user info card shows the real name/email from the `users` table for the logged-in user, plus a `member_since` string derived from `created_at`
- [ ] The summary stats (`total_spent`, `transaction_count`, `top_category`) match the actual sum/count/top category of that user's rows in `expenses`
- [ ] The transaction history table lists that user's real expenses, most recent first, with dates shown in `DD-MM-YYYY` format
- [ ] The category breakdown lists real per-category totals for that user, with percentages that sum to ~100% of `total_spent`
- [ ] A second user with different expenses sees only their own data when visiting `/profile` (no cross-user leakage)
- [ ] A freshly registered user with zero expenses can visit `/profile` without errors (empty/zero stats instead of a crash)
- [ ] App starts and runs (`python app.py`) without errors after the change
