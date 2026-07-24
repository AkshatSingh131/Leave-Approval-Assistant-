LEAVE_TYPES = [
    {"display": "Annual",           "slug": "annual",     "column": "annual_leave_balance",     "default_balance": 15},
    {"display": "Casual",           "slug": "casual",     "column": "casual_leave_balance",     "default_balance": 8},
    {"display": "Sick",             "slug": "sick",       "column": "sick_leave_balance",       "default_balance": 10},
    {"display": "Paid",             "slug": "paid",       "column": "paid_leave_balance",       "default_balance": 20},
    {"display": "Comp-Off",         "slug": "comp-off",   "column": "comp_off_leave_balance",   "default_balance": 5},
    {"display": "Work From Home",   "slug": "wfh",        "column": "wfh_leave_balance",        "default_balance": 12},
    {"display": "Maternity",        "slug": "maternity",  "column": "maternity_leave_balance",  "default_balance": 180},
    {"display": "Paternity",        "slug": "paternity",  "column": "paternity_leave_balance",  "default_balance": 15},
    {"display": "Bereavement",      "slug": "bereavement","column": "bereavement_leave_balance","default_balance": 5},
    {"display": "Marriage",         "slug": "marriage",   "column": "marriage_leave_balance",   "default_balance": 5},
    {"display": "Half-Day",         "slug": "half-day",   "column": "half_day_leave_balance",   "default_balance": 10},
    {"display": "Optional Holiday", "slug": "holiday",    "column": "holiday_leave_balance",    "default_balance": 2},
    {"display": "Loss of Pay",      "slug": "lwp",        "column": "lwp_leave_balance",        "default_balance": 999},
    {"display": "Emergency",        "slug": "emergency",  "column": "emergency_leave_balance",  "default_balance": 5},
    {"display": "Study",            "slug": "study",      "column": "study_leave_balance",      "default_balance": 10},
    {"display": "Sabbatical",       "slug": "sabbatical", "column": "sabbatical_leave_balance", "default_balance": 0},
]

# Convenience lookups
DISPLAY_NAMES = [lt["display"] for lt in LEAVE_TYPES]
SLUG_TO_DISPLAY = {lt["slug"]: lt["display"] for lt in LEAVE_TYPES}
DISPLAY_TO_SLUG = {lt["display"]: lt["slug"] for lt in LEAVE_TYPES}
SLUG_TO_COLUMN = {lt["slug"]: lt["column"] for lt in LEAVE_TYPES}


def slug_to_display(slug):
    """Fall back to the raw slug (capitalized) if it's somehow not in the table."""
    return SLUG_TO_DISPLAY.get(slug, slug.replace("-", " ").capitalize())
