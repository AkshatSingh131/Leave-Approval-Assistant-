import mysql.connector
import os
from dotenv import load_dotenv

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

    # Use a dictionary cursor only for the SELECT
    read_cursor = conn.cursor(dictionary=True)
    read_cursor.execute("SELECT * FROM leave_requests WHERE id = %s", (request_id,))
    request = read_cursor.fetchone()
    read_cursor.close()

    if not request:
        conn.close()
        return False

    # Use a plain cursor for all writes
    write_cursor = conn.cursor()

    write_cursor.execute(
        """UPDATE leave_requests
           SET status = %s, decided_by = %s, decided_on = NOW()
           WHERE id = %s""",
        (status, decided_by, request_id),
    )

    # Deduct from the correct leave balance only if approved
    if status == "approved":
        days = (request["end_date"] - request["start_date"]).days + 1
        leave_type = request["leave_type"]
        column_map = {
            "sick": "sick_leave_balance",
            "casual": "casual_leave_balance",
            "paid": "paid_leave_balance",
        }
        column = column_map.get(leave_type)
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
