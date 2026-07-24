from datetime import date
import bcrypt
from leave_types import LEAVE_TYPES


def validate_date_range(start_date, end_date):
    """Returns (True, None) if valid, or (False, error_message) if not."""
    if end_date < start_date:
        return False, "End date cannot be before start date."
    if start_date < date.today():
        return False, "Start date cannot be in the past."
    return True, None


def calculate_days(start_date, end_date):
    return (end_date - start_date).days + 1


def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def format_balance_summary(employee):
    """Takes an employee dict (from db.py) and returns a readable balance string
    covering all leave types defined in leave_types.py."""
    parts = [
        f"{lt['display']}: {employee.get(lt['column'], 0)} days"
        for lt in LEAVE_TYPES
    ]
    return " | ".join(parts)
