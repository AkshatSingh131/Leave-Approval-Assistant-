import streamlit as st
from datetime import date as date_cls
import requests

st.set_page_config(page_title="Leave Approval Assistant", layout="wide")

API_BASE = "http://localhost:5000/api"

# ─── Session State ────────────────────────────────────────────────────────────

if "user" not in st.session_state:
    st.session_state.user = None

# ─── API Helpers ──────────────────────────────────────────────────────────────

def api_get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=10)
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return {}

def api_post(path, data):
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, timeout=10)
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return {}

# ─── Leave type config ────────────────────────────────────────────────────────

LEAVE_TYPES = [
    {"display": "Annual",           "slug": "annual",       "column": "annual_leave_balance"},
    {"display": "Casual",           "slug": "casual",       "column": "casual_leave_balance"},
    {"display": "Sick",             "slug": "sick",         "column": "sick_leave_balance"},
    {"display": "Paid",             "slug": "paid",         "column": "paid_leave_balance"},
    {"display": "Comp-Off",         "slug": "comp-off",     "column": "comp_off_leave_balance"},
    {"display": "Work From Home",   "slug": "wfh",          "column": "wfh_leave_balance"},
    {"display": "Maternity",        "slug": "maternity",    "column": "maternity_leave_balance"},
    {"display": "Paternity",        "slug": "paternity",    "column": "paternity_leave_balance"},
    {"display": "Bereavement",      "slug": "bereavement",  "column": "bereavement_leave_balance"},
    {"display": "Marriage",         "slug": "marriage",     "column": "marriage_leave_balance"},
    {"display": "Half-Day",         "slug": "half-day",     "column": "half_day_leave_balance"},
    {"display": "Optional Holiday", "slug": "holiday",      "column": "holiday_leave_balance"},
    {"display": "Loss of Pay",      "slug": "lwp",          "column": "lwp_leave_balance"},
    {"display": "Emergency",        "slug": "emergency",    "column": "emergency_leave_balance"},
    {"display": "Study",            "slug": "study",        "column": "study_leave_balance"},
    {"display": "Sabbatical",       "slug": "sabbatical",   "column": "sabbatical_leave_balance"},
]

SLUG_TO_DISPLAY = {lt["slug"]: lt["display"] for lt in LEAVE_TYPES}

# ─── Auth ─────────────────────────────────────────────────────────────────────

def login_screen():
    st.title("Leave Management Login")
    email    = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        import db, utils
        employee = db.get_employee_by_email(email)
        if employee and utils.check_password(password, employee["password"]):
            st.session_state.user = employee
            st.rerun()
        else:
            st.error("Invalid email or password.")

# ─── Employee Dashboard ───────────────────────────────────────────────────────

def employee_dashboard(user):
    st.title(f"Welcome, {user['name']}")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Leave Balance", "Apply Leave", "My Requests", "Reporting Officer", "Holidays"
    ])

    # ── Leave Balance ──
    with tab1:
        st.subheader("Your Leave Balances")
        emp = api_get(f"/employee/{user['id']}/balance").get("balance", {})
        cols = st.columns(4)
        for i, lt in enumerate(LEAVE_TYPES):
            val = emp.get(lt["column"], 0)
            cols[i % 4].metric(lt["display"], f"{val} days")

    # ── Apply Leave ──
    with tab2:
        st.subheader("Apply for Leave")
        leave_display  = [lt["display"] for lt in LEAVE_TYPES]
        selected_display = st.selectbox("Leave Type", leave_display)
        selected_slug  = next(lt["slug"] for lt in LEAVE_TYPES if lt["display"] == selected_display)
        start_date     = st.date_input("Start Date", min_value=date_cls.today())
        end_date       = st.date_input("End Date",   min_value=date_cls.today())
        reason         = st.text_area("Reason")

        if st.button("Submit Request"):
            if end_date < start_date:
                st.error("End date cannot be before start date.")
            else:
                res = api_post("/leave/apply", {
                    "employee_id": user["id"],
                    "leave_type":  selected_slug,
                    "start_date":  str(start_date),
                    "end_date":    str(end_date),
                    "reason":      reason,
                })
                if res.get("success"):
                    st.success("Leave request submitted successfully.")
                else:
                    st.error("Something went wrong.")

    # ── My Requests ──
    with tab3:
        st.subheader("My Leave History")
        data = api_get(f"/leave/employee/{user['id']}").get("requests", [])
        if not data:
            st.write("No leave requests yet.")
        else:
            for r in data:
                status_color = {
                    "pending":   "🟡",
                    "approved":  "🟢",
                    "rejected":  "🔴",
                    "cancelled": "⚫",
                }.get(r["status"], "⚪")
                start = str(r["start_date"])[:10]
                end   = str(r["end_date"])[:10]
                st.write(
                    f"{status_color} **{SLUG_TO_DISPLAY.get(r['leave_type'], r['leave_type'])}** | "
                    f"{start} → {end} | {r['status'].capitalize()}"
                )
                if r.get("reason"):
                    st.caption(f"Reason: {r['reason']}")

    # ── Reporting Officer ──
    with tab4:
        st.subheader("Your Reporting Officer")
        officer = api_get(f"/employee/{user['id']}/reporting-officer").get("reporting_officer")
        if officer:
            st.write(f"**Name:** {officer['name']}")
            st.write(f"**Email:** {officer['email']}")
        else:
            st.write("No reporting officer assigned.")

    # ── Holidays ──
    with tab5:
        st.subheader("Holiday List 2026")
        holidays = api_get("/holidays").get("holidays", [])
        if holidays:
            for h in holidays:
                badge = "🏛️" if h["type"] == "national" else "📅"
                st.write(f"{badge} **{h['name']}** — {str(h['date'])[:10]}")
        else:
            st.write("No holidays found.")

# ─── Approver Dashboard ───────────────────────────────────────────────────────

def approver_dashboard(user):
    st.title(f"Approver Dashboard — {user['name']}")
    tab1, tab2, tab3, tab4 = st.tabs([
        "Pending Requests", "Team Calendar", "Holidays", "AI Assistant"
    ])

    # ── Pending Requests ──
    with tab1:
        st.subheader("Pending Leave Requests")
        pending = api_get(f"/leave/pending/{user['id']}").get("requests", [])

        if not pending:
            st.write("No pending requests.")
        else:
            for req in pending:
                with st.container(border=True):
                    start = str(req["start_date"])[:10]
                    end   = str(req["end_date"])[:10]
                    days  = (date_cls.fromisoformat(end) - date_cls.fromisoformat(start)).days + 1
                    st.write(
                        f"**{req['employee_name']}** — "
                        f"{SLUG_TO_DISPLAY.get(req['leave_type'], req['leave_type'])} leave | "
                        f"{start} → {end} ({days} days)"
                    )
                    if req.get("reason"):
                        st.caption(f"Reason: {req['reason']}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✅ Approve", key=f"approve_{req['id']}"):
                            api_post("/leave/status", {
                                "request_id": req["id"],
                                "status":     "approved",
                                "decided_by": user["id"],
                            })
                            st.rerun()
                    with col2:
                        if st.button("❌ Reject", key=f"reject_{req['id']}"):
                            api_post("/leave/status", {
                                "request_id": req["id"],
                                "status":     "rejected",
                                "decided_by": user["id"],
                            })
                            st.rerun()
                    with col3:
                        if st.button("🚫 Cancel", key=f"cancel_{req['id']}"):
                            api_post("/leave/cancel", {
                                "request_id":   req["id"],
                                "cancelled_by": user["id"],
                            })
                            st.rerun()

    # ── Team Calendar ──
    with tab2:
        st.subheader("Team Leave Calendar")
        leaves = api_get(f"/team/{user['id']}/calendar").get("leaves", [])
        if not leaves:
            st.write("No upcoming leaves for your team.")
        else:
            for l in leaves:
                status_color = {"pending": "🟡", "approved": "🟢"}.get(l["status"], "⚪")
                start = str(l["start_date"])[:10]
                end   = str(l["end_date"])[:10]
                st.write(
                    f"{status_color} **{l['employee_name']}** — "
                    f"{SLUG_TO_DISPLAY.get(l['leave_type'], l['leave_type'])} | "
                    f"{start} → {end}"
                )

    # ── Holidays ──
    with tab3:
        st.subheader("Holiday List 2026")
        holidays = api_get("/holidays").get("holidays", [])
        if holidays:
            for h in holidays:
                badge = "🏛️" if h["type"] == "national" else "📅"
                st.write(f"{badge} **{h['name']}** — {str(h['date'])[:10]}")
        else:
            st.write("No holidays found.")

    # ── AI Assistant ──
    with tab4:
        st.subheader("AI Leave Assistant")
        question = st.text_input("Ask anything about leaves")
        if st.button("Ask"):
            res = api_post("/chat", {
                "user": {
                    "id":   user["id"],
                    "name": user["name"],
                    "role": user["role"],
                },
                "question": question,
            })
            st.write(res.get("answer", "No response."))

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if st.session_state.user is None:
        login_screen()
    else:
        user = st.session_state.user
        if st.sidebar.button("Logout"):
            st.session_state.user = None
            st.rerun()
        st.sidebar.write(f"Logged in as **{user['name']}**")
        st.sidebar.write(f"Role: `{user['role']}`")

        if user["role"] == "approver":
            approver_dashboard(user)
        else:
            employee_dashboard(user)


if __name__ == "__main__":
    main()
