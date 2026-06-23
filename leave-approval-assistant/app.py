import streamlit as st
from datetime import date
import db
import utils
import chatbot

st.set_page_config(page_title="Leave Approval Assistant", layout="centered")

if "user" not in st.session_state:
    st.session_state.user = None


def login_screen():
    st.title("Leave Management Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        employee = db.get_employee_by_email(email)
        if employee and utils.check_password(password, employee["password"]):
            st.session_state.user = employee
            st.rerun()
        else:
            st.error("Invalid email or password.")


def employee_dashboard(user):
    st.title(f"Welcome, {user['name']}")
    st.subheader("Your Leave Balances")
    st.write(utils.format_balance_summary(user))

    st.subheader("Apply for Leave")
    leave_type = st.selectbox("Leave Type", ["sick", "casual", "paid"])
    start_date = st.date_input("Start Date", min_value=date.today())
    end_date = st.date_input("End Date", min_value=date.today())
    reason = st.text_area("Reason")

    if st.button("Submit Request"):
        valid, error = utils.validate_date_range(start_date, end_date)
        if not valid:
            st.error(error)
        else:
            success = db.create_leave_request(user["id"], leave_type, start_date, end_date, reason)
            if success:
                st.success("Leave request submitted.")
            else:
                st.error("Something went wrong submitting your request.")

    st.subheader("Your Past Requests")
    requests = db.get_requests_for_employee(user["id"])
    if requests:
        for r in requests:
            st.write(
                f"**{r['leave_type'].capitalize()}** | {r['start_date']} to {r['end_date']} "
                f"| Status: {r['status']}"
            )
    else:
        st.write("No leave requests yet.")


def approver_dashboard(user):
    st.title(f"Approver Dashboard — {user['name']}")

    st.subheader("Pending Requests")
    pending = db.get_pending_requests_for_approver(user["id"])

    if not pending:
        st.write("No pending requests.")
    else:
        for req in pending:
            with st.container(border=True):
                st.write(
                    f"**{req['employee_name']}** — {req['leave_type'].capitalize()} leave, "
                    f"{req['start_date']} to {req['end_date']}"
                )
                st.write(f"Reason: {req['reason']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Approve", key=f"approve_{req['id']}"):
                        db.update_leave_status(req["id"], "approved", user["id"])
                        st.rerun()
                with col2:
                    if st.button("Reject", key=f"reject_{req['id']}"):
                        db.update_leave_status(req["id"], "rejected", user["id"])
                        st.rerun()

    st.subheader("Ask the Assistant")
    question = st.text_input("Ask a question about pending requests")
    if st.button("Ask"):
        answer = chatbot.ask_chatbot(user["id"], question)
        st.write(answer)


def main():
    if st.session_state.user is None:
        login_screen()
    else:
        user = st.session_state.user
        if st.sidebar.button("Logout"):
            st.session_state.user = None
            st.rerun()

        if user["role"] == "approver":
            approver_dashboard(user)
        else:
            employee_dashboard(user)


if __name__ == "__main__":
    main()
