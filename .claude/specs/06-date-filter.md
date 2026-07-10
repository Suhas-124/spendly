---
# Spec: Date Filter

## Overview
This step adds date-range filtering to the profile page. Step 5 wired `/profile` to real queries scoped to the logged-in user's full expense history; this step layers an optional date filter on top so a user can narrow the summary stats, transaction history, and category breakdown to a specific time window (e.g. "This Month", "Last Month", "Last 30 Days", or a custom range) instead of always seeing all-time totals. No new route is introduced — `GET /profile` is extended to read filter parameters from the query string, defaulting to "All Time" (identical to today's behavior) when none are supplied.

## Depends on
- Step 1 (Database Setup) — requires `database/db.py`'s `get_db()` and the `expenses` table (`user_id`, `amount`, `category`, `date`, `description`).
- Step 3 (Login and Logout) — requires `session['user_id']` to be set for the logged-in user.
- Step 4 (Profile Page Creation) — requires `templates/profile.html` and the `login_required` guard on `/profile`.
- Step 5 (Backend Routes for Profile Page) — requires `/profile` to already derive `user`, `stats`, `transactions`, `categories` from real DB queries; this step adds filtering on top of those same queries rather than replacing them.

## Routes
- `GET /profile` — unchanged path and access level (logged-in only), but now reads optional query-string parameters:
  - `range` — one of `all`, `this_month`, `last_month`, `last_30`, `custom` (default `all` if absent or unrecognized)
  - `start_date`, `end_date` — `YYYY-MM-DD`, only used when `range=custom`; if either is missing/invalid when `range=custom`, fall back to `all` and show a validation message rather than erroring

## Database changes
No database changes. The existing `expenses.date` column (`YYYY-MM-DD` TEXT) is sufficient for range filtering with `date BETWEEN ? AND ?`.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — add a filter control above the stats/transactions sections:
  - A `GET` form (submits to `/profile`, preserving query params) with a `<select name="range">` for the presets (All Time / This Month / Last Month / Last 30 Days / Custom), plus two `<input type="date">` fields (`start_date`, `end_date`) that are only relevant/enabled when "Custom" is selected.
  - Selected preset and custom dates must reflect the current request's query params (`{{ selected_range }}`, `{{ start_date }}`, `{{ end_date }}`) so the form doesn't reset itself after submission.
  - If `range=custom` was submitted with invalid/missing dates, show the same validation message pattern used elsewhere in the app (e.g. reuse `.error`/`.form-error` styling already defined in `style.css`).

## Files to change
- `app.py` — extend the `/profile` view:
  - Read `range`, `start_date`, `end_date` from `request.args`.
  - Compute the effective `(start_date, end_date)` SQL bounds from the selected preset using Python's `datetime`/`calendar` (already-imported `datetime`, plus `calendar` from the standard library if needed for month boundaries):
    - `this_month` — first day of current month through today
    - `last_month` — first through last day of the previous calendar month
    - `last_30` — today minus 29 days through today
    - `custom` — the submitted `start_date`/`end_date`, validated as parseable `YYYY-MM-DD` and `start_date <= end_date`
    - `all` (default) — no date bound applied
  - Apply the computed bounds (when present) to the `stats`, `transactions`, and `categories` queries via `AND date BETWEEN ? AND ?`, keeping every query parameterized and scoped to `user_id = ?`.
  - Pass `selected_range`, `start_date`, `end_date`, and an optional `filter_error` into the template context alongside the existing `user`, `stats`, `transactions`, `categories`.
  - Keep the "5 most recent transactions" limit behavior for `transactions` within the filtered window (still `ORDER BY date DESC LIMIT 5`).
- `templates/profile.html` — add the filter form and wire it to the new context variables, per **Templates** above.
- `static/css/style.css` — add styling for the new filter control (a `.profile-filter*` component group), using existing CSS variables (`--border*`, `--radius-sm/md`, `--font-body`, etc.) — no new hardcoded colors.

## Files to create
None.

## New dependencies
No new dependencies. `datetime` is already imported in `app.py`; `calendar` (standard library) may be added for month-boundary math if convenient.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL, always filter by `user_id = ?` and use `?` placeholders for date bounds
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Every filtered query must remain scoped to the logged-in `user_id` — never return another user's expenses
- Invalid `range` values or invalid `custom` dates must degrade gracefully to `all` (or show a validation message) — never raise a 500
- Handle the zero-results-in-range case gracefully: `total_spent` is `0.0`, `transaction_count` is `0`, `top_category` is `"—"`, and the transaction/category lists are empty without raising an error
- Keep the exact same context variable names/shapes for `user`, `stats`, `transactions`, `categories` that `templates/profile.html` already expects from Step 5 — only add new variables, don't rename existing ones

## Definition of done
- [ ] Visiting `/profile` with no query params behaves exactly as it did after Step 5 (all-time stats, transactions, categories)
- [ ] Visiting `/profile?range=this_month` shows stats/transactions/categories limited to the current calendar month only
- [ ] Visiting `/profile?range=last_month` shows stats/transactions/categories limited to the previous calendar month only
- [ ] Visiting `/profile?range=last_30` shows stats/transactions/categories limited to the last 30 days
- [ ] Visiting `/profile?range=custom&start_date=...&end_date=...` with valid dates filters correctly to that inclusive range
- [ ] Visiting `/profile?range=custom` with a missing or invalid date falls back to all-time data and displays a validation message instead of erroring
- [ ] The filter form on the page reflects the currently applied filter (selected preset / populated custom dates) after submission
- [ ] A user with zero expenses in the selected range sees zero/empty stats, not a crash
- [ ] A second user's expenses are never included in the filtered results for the logged-in user (no cross-user leakage)
- [ ] App starts and runs (`python app.py`) without errors after the change
