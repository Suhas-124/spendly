# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove an expense they no longer
want tracked (e.g. a duplicate or mistaken entry). The route already exists
as a GET-only placeholder at `/expenses/<id>/delete`; this step upgrades it
to a POST-only handler that verifies ownership, deletes the row, and
redirects back to the profile page. A "Delete" button is added next to the
existing "Edit" link on each row of the profile page's transaction table,
guarded by a plain-JS confirmation prompt so a user can't delete an expense
with a single accidental click.

## Depends on
- Step 1: Database setup (`expenses` table exists)
- Step 3: Login / Logout (`session["user_id"]` is set and checked)
- Step 4 / 5: Profile page exists and is the redirect target after deleting
- Step 8: Edit Expense (`get_expense` ownership-lookup helper and the
  `/expenses/<id>/...` route/table-row pattern are reused here)

## Routes
- `POST /expenses/<id>/delete` — delete the expense and redirect to
  `/profile` — logged-in only, owner only

No `GET /expenses/<id>/delete` — deleting is a destructive action and must
not be triggerable by a plain link/GET request (crawlers, browser
prefetching, etc.). The existing GET-only placeholder route is replaced,
not kept alongside the POST route.

## Database changes
No database changes. Deleting only requires the existing `id` and
`user_id` columns on the `expenses` table.

## Templates
- **Modify:** `templates/profile.html`
  - Add a "Delete" button next to the existing "Edit" link in the Actions
    column of each transaction row
  - The button lives in its own small `<form method="POST" action="{{ url_for('delete_expense', id=tx.id) }}">`
    so it performs a real POST instead of a link-triggered GET
  - The form's `onsubmit` calls a plain JS `confirm(...)` prompt ("Delete
    this expense? This cannot be undone.") — submission is cancelled if the
    user declines

## Files to change
- `app.py`
  - Replace the placeholder `/expenses/<int:id>/delete` route with a
    POST-only handler:
    - Look up the expense via the existing `get_expense(id, session["user_id"])`
      helper; if it doesn't exist or belongs to another user, return 404
    - Call a new `delete_expense` query helper, then redirect to
      `url_for("profile")`
- `database/queries.py` — add a `delete_expense(expense_id)` function that
  deletes the row by `id` (ownership is already verified by the route via
  `get_expense` before this is called, same pattern as `update_expense`)
- `templates/profile.html` — add the Delete form/button per transaction row

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Foreign keys PRAGMA must be enabled on every connection (already done in
  `get_db()`)
- Unauthenticated POST to `/expenses/<id>/delete` must redirect to `/login`
- An authenticated user posting to an expense `id` that doesn't exist, or
  that belongs to a different user, must get a 404 — never allow deleting
  another user's expense (reuse the same `get_expense` ownership check
  already used by `edit_expense`)
- The delete action must only be reachable via POST — no GET route, no
  plain `<a href>` link performing the delete
- The confirmation prompt is plain JS (`confirm()`) — no new JS framework,
  consistent with `static/js/main.js` being the only place for vanilla JS
  beyond inline `{% block scripts %}`
- After a successful delete, redirect to `url_for("profile")`
- Use CSS variables — never hardcode hex values (reuse the existing
  `--danger` / `--danger-light` variables already defined in
  `static/css/style.css` for the delete button's styling)
- All templates extend `base.html`
- No inline styles

## Definition of done
- [ ] Sending a GET request to `/expenses/<id>/delete` no longer deletes
      anything (no GET route exists for this path)
- [ ] Posting to `/expenses/<id>/delete` while logged out redirects to
      `/login`
- [ ] Posting to `/expenses/<id>/delete` for an expense that doesn't belong
      to the logged-in user returns a 404 and the expense is not deleted
- [ ] Posting to `/expenses/<id>/delete` for an expense the logged-in user
      owns removes it from the database and redirects to `/profile`
- [ ] The deleted expense no longer appears in the profile page's
      transaction list, stats, or category breakdown
- [ ] Each transaction row on the profile page has a "Delete" button that
      prompts for confirmation before submitting
- [ ] Declining the confirmation prompt does not delete the expense
