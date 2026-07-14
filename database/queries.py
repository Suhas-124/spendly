from database.db import get_db


def insert_expense(user_id, amount, category, date, description):
    conn = get_db()
    conn.execute(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, amount, category, date, description),
    )
    conn.commit()
    conn.close()


def get_expense(expense_id, user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()
    conn.close()
    return row


def update_expense(expense_id, amount, category, date, description):
    conn = get_db()
    conn.execute(
        """
        UPDATE expenses
        SET amount = ?, category = ?, date = ?, description = ?
        WHERE id = ?
        """,
        (amount, category, date, description, expense_id),
    )
    conn.commit()
    conn.close()
