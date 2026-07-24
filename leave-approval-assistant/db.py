import mysql.connector
import os
from dotenv import load_dotenv
from leave_types import SLUG_TO_COLUMN

load_dotenv()


def get_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None


def get_employee_by_email(email):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees WHERE email = %s", (email,))
    employee = cursor.fetchone()

    cursor.close()
    conn.close()
    return employee


def get_employee_by_id(employee_id):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
    employee = cursor.fetchone()

    cursor.close()
    conn.close()
    return employee


def create_leave_request(employee_id, leave_type, start_date, end_date, reason):
    conn = get_connection()
    if not conn:
        return False

    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, reason)
           VALUES (%s, %s, %s, %s, %s)""",
        (employee_id, leave_type, start_date, end_date, reason),
    )
    conn.commit()

    cursor.close()
    conn.close()
    return True


def get_pending_requests_for_approver(approver_id):
    conn = get_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT lr.*, e.name AS employee_name
           FROM leave_requests lr
           JOIN employees e ON lr.employee_id = e.id
           WHERE e.manager_id = %s AND lr.status = 'pending'
           ORDER BY lr.applied_on ASC""",
        (approver_id,),
    )
    requests = cursor.fetchall()

    cursor.close()
    conn.close()
    return requests


def get_requests_for_employee(employee_id):
    conn = get_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT * FROM leave_requests
           WHERE employee_id = %s
           ORDER BY applied_on DESC""",
        (employee_id,),
    )
    requests = cursor.fetchall()

    cursor.close()
    conn.close()
    return requests


def update_leave_status(request_id, status, decided_by):
    """status should be 'approved' or 'rejected'."""
    conn = get_connection()
    if not conn:
        return False

    
    read_cursor = conn.cursor(dictionary=True)
    read_cursor.execute("SELECT * FROM leave_requests WHERE id = %s", (request_id,))
    request = read_cursor.fetchone()
    read_cursor.close()

    if not request:
        conn.close()
        return False

    
    write_cursor = conn.cursor()

    write_cursor.execute(
        """UPDATE leave_requests
           SET status = %s, decided_by = %s, decided_on = NOW()
           WHERE id = %s""",
        (status, decided_by, request_id),
    )

    
    if status == "approved":
        days = (request["end_date"] - request["start_date"]).days + 1
        leave_type = request["leave_type"]
        column = SLUG_TO_COLUMN.get(leave_type)
        
        if column:
            write_cursor.execute(
                f"""UPDATE employees
                    SET {column} = {column} - %s
                    WHERE id = %s""",
                (days, request["employee_id"]),
            )

    conn.commit()
    write_cursor.close()
    conn.close()
    return True

# ── Paste these functions into your existing db.py ──────────────────────────
# Add them before the execute_readonly_query function.

def cancel_leave_request(request_id, cancelled_by):
    """Approver cancels a pending leave request.
    If the request was already approved, restores the employee's balance."""
    conn = get_connection()
    if not conn:
        return False

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leave_requests WHERE id = %s", (request_id,))
    request = cursor.fetchone()

    if not request:
        cursor.close()
        conn.close()
        return False

    # Only allow cancelling pending or approved requests
    if request["status"] == "rejected":
        cursor.close()
        conn.close()
        return False

    # If it was approved, restore the balance
    if request["status"] == "approved":
        days = (request["end_date"] - request["start_date"]).days + 1
        leave_type = request["leave_type"]
        column = SLUG_TO_COLUMN.get(leave_type)
        if column:
            cursor.execute(
                f"""UPDATE employees
                    SET {column} = {column} + %s
                    WHERE id = %s""",
                (days, request["employee_id"]),
            )

    cursor.execute(
        """UPDATE leave_requests
           SET status = 'cancelled', decided_by = %s, decided_on = NOW()
           WHERE id = %s""",
        (cancelled_by, request_id),
    )

    conn.commit()
    cursor.close()
    conn.close()
    return True


def get_reporting_officer(employee_id):
    """Returns the manager (approver) for a given employee."""
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT m.id, m.name, m.email
           FROM employees e
           JOIN employees m ON e.manager_id = m.id
           WHERE e.id = %s""",
        (employee_id,),
    )
    officer = cursor.fetchone()
    cursor.close()
    conn.close()
    return officer


def get_team_leave_calendar(approver_id):
    """Returns all approved/pending leaves for the approver's team,
    useful for rendering a calendar view."""
    conn = get_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT lr.id, e.name AS employee_name, lr.leave_type,
                  lr.start_date, lr.end_date, lr.status
           FROM leave_requests lr
           JOIN employees e ON lr.employee_id = e.id
           WHERE e.manager_id = %s
             AND lr.status IN ('pending', 'approved')
           ORDER BY lr.start_date ASC""",
        (approver_id,),
    )
    leaves = cursor.fetchall()
    cursor.close()
    conn.close()
    return leaves


def get_holidays():
    """Returns all holidays from the holidays table."""
    conn = get_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM holidays ORDER BY date ASC")
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


def execute_readonly_query(sql):
    """Executes a SELECT-only query and returns results as a list of dicts.
    Rejects anything that isn't a SELECT, to prevent destructive queries
    (e.g. from an LLM-generated query) from ever running."""
    cleaned = sql.strip().rstrip(";")

    if not cleaned.lower().startswith("select"):
        return {"error": "Only SELECT queries are allowed."}

    
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "create", ";"]
    lowered = cleaned.lower()
    if any(word in lowered for word in forbidden):
        return {"error": "Query contains disallowed keywords."}

    conn = get_connection()
    if not conn:
        return {"error": "Could not connect to database."}

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(cleaned)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"rows": rows}
    except mysql.connector.Error as err:
        conn.close()
        return {"error": str(err)}

def get_employee_by_name(name):
    """Looks up an employee by their name column (case-insensitive)."""
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees WHERE LOWER(name) = LOWER(%s)", (name,))
    employee = cursor.fetchone()
    cursor.close()
    conn.close()
    return employee

if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("Connected successfully")
        conn.close()
    else:
        print("Connection failed")
