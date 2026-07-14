# Spec: Edit Expenses

## Overview
Step 8 lets a logged-in user correct a mistake in an existing expense (wrong
amount, category, date, or description) without deleting and re-adding it.
The route already exists as a GET-only placeholder at `/expenses/<id>/edit`;
this step upgrades it to a full GET + POST handler that loads the expense,
verifies the logged-in user owns it, pre-fills a form with its current
values, validates submitted changes using the same rules as Step 7, and
updates the row in place. An "Edit" link is added to each row of the
transaction table on the profile page so users can reach the form.

## Depends on
- Step 1: Database setup (`expenses` table exists with all required columns)
- Step 3: Login / Logout (`session["user_id"]` is set and checked)
- Step 4 / 5: Profile page exists and is the redirect target after saving
- Step 7: Add Expense (`EXPENSE_CATEGORIES`, validation rules, and
  `add_expense.html` form markup are reused here)

## Routes
- `GET /expenses/<id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in only, owner only
- `POST /expenses/<id>/edit` — validate and update the expense — logged-in
  only, owner only

## Database changes
No database changes. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`
  - Same field set and layout as `templates/add_expense.html`:
    - `amount` — number input, step="0.01", min="0.01", required
    - `category` — `<select>` with the 7 fixed options: Food, Transport,
      Bills, Health, Entertainment, Shopping, Other
    - `date` — `<input type="date">`, required
    - `description` — text input, optional, max 200 chars
  - Form `method="POST"` and `action="{{ url_for('edit_expense', id=expense.id) }}"`
  - All fields pre-filled with the expense's current values (or previously
    submitted values on a validation error)
  - Submit button ("Save Changes") and a cancel link back to `/profile`
  - Display error message when validation fails, re-populating submitted values
- **Modify:** `templates/profile.html`
  - Add an "Edit" link/button in each transaction row pointing to
    `/expenses/<id>/edit`

## Files to change
- `app.py`
  - Replace the placeholder `/expenses/<int:id>/edit` route with a GET+POST
    handler:
    - GET: look up the expense by `id`; if it doesn't exist or
      `user_id` doesn't match `session["user_id"]`, return 404; otherwise
      render `edit_expense.html` with the expense's current values
    - POST: same lookup/ownership check, then validate form fields (reuse the
      Step 7 rules), call an update query, and redirect to `/profile`
  - Add `id` to the columns selected in the `profile()` transaction query so
    `templates/profile.html` can build the edit link for each row
- `database/queries.py` — add a query function to fetch a single expense by
  `id` (scoped to `user_id`) and a query function to update an expense's
  `amount`, `category`, `date`, and `description` by `id`
- `templates/profile.html` — add an "Edit" link per transaction row

## Files to create
- `templates/edit_expense.html` — the edit-expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (unaffected by this feature, but stays true
  for the app as a whole)
- Foreign keys PRAGMA must be enabled on every connection (already done in
  `get_db()`)
- Unauthenticated access to both GET and POST `/expenses/<id>/edit` must
  redirect to `/login`
- An authenticated user requesting an expense `id` that doesn't exist, or
  that belongs to a different user, must get a 404 — never leak another
  user's expense data and never allow editing it
- Validation rules for POST (identical to Step 7):
  - `amount`: required, must be a positive number greater than 0 (parse with
    `float()`; catch `ValueError`)
  - `category`: required, must be one of the 7 fixed categories (reject
    anything else)
  - `date`: required, must be a valid `YYYY-MM-DD` date (parse with
    `datetime.strptime`)
  - `description`: optional; strip whitespace; store `None` if blank
  - On any validation error, re-render the form with the error message and
    the submitted values pre-filled (not the original DB values)
- After a successful update, redirect to `url_for("profile")` — do NOT
  render the form again
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency must always display as ₹ — never £ or $

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that doesn't belong to the
      logged-in user returns a 404
- [ ] Visiting `/expenses/<id>/edit` for an expense that belongs to the
      logged-in user shows a form pre-filled with its current amount,
      category, date, and description
- [ ] Submitting a valid change redirects to `/profile` and the updated
      values appear in the transaction list
- [ ] Submitting with a missing or zero amount re-renders the form with an
      error and the submitted values retained
- [ ] Submitting with an invalid category re-renders the form with an error
- [ ] Submitting with an invalid date re-renders the form with an error
- [ ] Clearing the description and submitting saves the expense with no
      description (no error)
- [ ] Each row in the profile page's transaction table has a working "Edit"
      link that navigates to `/expenses/<id>/edit`
