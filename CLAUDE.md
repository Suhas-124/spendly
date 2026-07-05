# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Spendly — a Flask personal expense tracker built as a **teaching skeleton**. Core features (database, auth, expense CRUD) are intentionally left as stubs marked `# Students will write this... — Step N` / `coming in Step N`. When asked to implement one of these, follow the numbered step it's associated with and don't jump ahead to unrelated stubs.

## Running the app

```bash
source evenv/bin/activate   # bare `python`/`pip` are not on PATH otherwise
python app.py                # Flask dev server on 0.0.0.0:5000, debug=True
```

There is no build step, linter, or test command configured yet (`pytest`/`pytest-flask` are in requirements.txt but no tests exist).

## Architecture

- **`app.py`** — single-file Flask app; all routes live here (no blueprints). Working routes: `/`, `/register`, `/login`, `/terms`, `/privacy`. Stub routes (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) currently just return a plain string — implementing these is expected future work, not a bug.
- **`database/db.py`** — currently empty (comment-only stub). Intended to hold `get_db()` (SQLite connection, row_factory + foreign keys on), `init_db()` (CREATE TABLE IF NOT EXISTS), and `seed_db()` (sample data).
- **Templates use Jinja2 inheritance**: `templates/base.html` is the shared shell (navbar, `<footer>`, font links, `static/css/style.css`) with blocks `{% block title %}`, `{% block head %}`, `{% block content %}`, `{% block scripts %}`. Every page template `{% extends "base.html" %}` and only fills in blocks — don't duplicate the navbar/footer in individual page templates.
  - **The footer lives only in `base.html`**, not in `landing.html` or any other page — if a task references "the footer link on the landing page," the actual edit target is `base.html`.
- **`static/css/style.css`** is the single stylesheet for the whole app (no per-page CSS files). It's organized as one design system:
  - CSS custom properties in `:root` (`--ink*`, `--paper*`, `--accent`/`--accent-2`/`--danger` + `-light` variants, `--border*`, `--font-display`/`--font-body`, `--max-width`, `--auth-width`, `--radius-sm/md/lg`).
  - Reusable component classes: `.hero*`, `.mock-card` (+ `.mock-dots`/`.mock-stats`/`.mock-bars-card` etc. for the dashboard-preview mockup in the hero), `.btn-primary`/`.btn-ghost`, `.features*`, `.cta*`, `.auth*` (register/login forms), `.legal-*` (terms/privacy pages).
  - Responsive breakpoints at `@media (max-width: 900px)` and `(max-width: 600px)`.
  - When editing one component's styles, check whether a class (e.g. `.hero-badge`) is also shared by another page (e.g. the "Legal" badge on terms/privacy) before changing its base rule — scope new variants with a more specific selector instead of overwriting the shared one.
- **`static/js/main.js`** — currently just a placeholder comment; no JS framework is used anywhere in the project. Any interactive behavior (e.g. modals) should be added as vanilla JS, either here or in a page's `{% block scripts %}`.
- **`insights-report.html`** at the repo root is an unrelated, untracked generated artifact — don't stage or reference it as part of app functionality.
