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
