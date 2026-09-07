import sqlite3
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import date, datetime

DB_PATH = Path(__file__).with_name("expenses.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def normalize_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m.%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Invalid date: {value}")


def money(value):
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError("Invalid amount.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return amount.quantize(Decimal("0.01"))


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                recurrence_id TEXT,
                recurrence_frequency TEXT NOT NULL DEFAULT 'none',
                start_date TEXT,
                end_date TEXT
            )
        """)

        conn.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        month TEXT NOT NULL UNIQUE
    )
    """)

        columns = {r[1] for r in conn.execute("PRAGMA table_info(expenses)")}

        # Migrate older databases while keeping all existing expense records.
        if "date" not in columns and "expense_date" in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN date TEXT")
            conn.execute("UPDATE expenses SET date = expense_date WHERE date IS NULL")

        if "description" in columns:
            conn.execute("UPDATE expenses SET description='' WHERE description IS NULL")

        if "recurrence_id" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN recurrence_id TEXT")
        if "recurrence_frequency" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN recurrence_frequency TEXT NOT NULL DEFAULT 'none'")

        if "start_date" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN start_date TEXT")
        if "end_date" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN end_date TEXT")

        conn.execute("UPDATE expenses SET start_date = date WHERE start_date IS NULL OR TRIM(start_date) = ''")
        conn.execute("UPDATE expenses SET end_date = COALESCE(end_date, start_date, date) WHERE end_date IS NULL OR TRIM(end_date) = ''")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_start_date ON expenses(start_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_end_date ON expenses(end_date)")
        conn.commit()


def get_expenses():
    initialize_database()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, amount, category, description,
                   COALESCE(start_date, date), COALESCE(end_date, start_date, date)
            FROM expenses
            ORDER BY COALESCE(start_date, date) DESC, id DESC
        """).fetchall()

    result = []
    for row in rows:
        start = normalize_date(row[4])
        end = normalize_date(row[5])
        result.append((row[0], row[1], row[2], row[3] or "", start.isoformat(), end.isoformat()))
    return result


def insert_expense(amount, category, description, start_date, end_date=None):
    initialize_database()
    amount = money(amount)
    category = str(category or "").strip()
    description = str(description or "").strip()
    start = normalize_date(start_date)
    end = normalize_date(end_date if end_date is not None else start)

    if not category:
        raise ValueError("Category is required.")
    if end < start:
        raise ValueError("End date cannot be earlier than start date.")

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO expenses
            (amount, category, description, date, recurrence_id, recurrence_frequency, start_date, end_date)
            VALUES (?, ?, ?, ?, NULL, 'none', ?, ?)
        """, (float(amount), category, description, start.isoformat(), start.isoformat(), end.isoformat()))
        conn.commit()


def update_expense(expense_id, amount, category, description, start_date, end_date=None):
    initialize_database()
    amount = money(amount)
    category = str(category or "").strip()
    description = str(description or "").strip()
    start = normalize_date(start_date)
    end = normalize_date(end_date if end_date is not None else start)

    if not category:
        raise ValueError("Category is required.")
    if end < start:
        raise ValueError("End date cannot be earlier than start date.")

    with get_connection() as conn:
        current = conn.execute("SELECT id FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not current:
            raise ValueError("Expense no longer exists.")
        conn.execute("""
            UPDATE expenses
            SET amount=?, category=?, description=?, date=?, start_date=?, end_date=?,
                recurrence_id=NULL, recurrence_frequency='none'
            WHERE id=?
        """, (float(amount), category, description, start.isoformat(), start.isoformat(), end.isoformat(), expense_id))
        conn.commit()


def delete_expense(expense_id):
    initialize_database()
    with get_connection() as conn:
        conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        conn.commit()


def insert_income(amount, month):
    initialize_database()

    amount = money(amount)
    month = str(month).strip()

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise ValueError("Invalid month. Use YYYY-MM.")

    with get_connection() as conn:
        existing = conn.execute("""
            SELECT id
            FROM income
            WHERE month = ?
        """, (month,)).fetchone()

        if existing:
            conn.execute("""
                UPDATE income
                SET amount = ?
                WHERE month = ?
            """, (float(amount), month))
        else:
            conn.execute("""
                INSERT INTO income (amount, month)
                VALUES (?, ?)
            """, (float(amount), month))

        conn.commit()

def get_income(month):
    initialize_database()

    month = str(month).strip()

    with get_connection() as conn:
        row = conn.execute("""
            SELECT amount
            FROM income
            WHERE month = ?
        """, (month,)).fetchone()

    if row is None:
        return Decimal("0")

    return Decimal(str(row[0]))



def insert_expense_series(*args, **kwargs):
    """Backward-compatible wrapper: recurring series are no longer generated."""
    return insert_expense(*args[:5]) if len(args) >= 5 else insert_expense(*args, **kwargs)


def edit_expense(expense_id, amount, category, description, start_date, end_date=None):
    return update_expense(expense_id, amount, category, description, start_date, end_date)


def remove_expense(expense_id):
    return delete_expense(expense_id)


def get_total_expenses():
    initialize_database()
    with get_connection() as conn:
        row = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()
    return money(row[0] or 0)


initialize_database()
