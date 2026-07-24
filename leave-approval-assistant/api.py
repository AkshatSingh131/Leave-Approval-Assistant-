from flask import Flask, request, jsonify
import db

app = Flask(__name__)
app.config["JSON_PROVIDER_CLASS"] = None

from flask.json.provider import DefaultJSONProvider
import datetime

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)

app.json_provider_class = CustomJSONProvider
app.json = CustomJSONProvider(app)

# ─── Leave Requests ───────────────────────────────────────────────────────────

@app.route("/api/leave/apply", methods=["POST"])
def apply_leave():
    data = request.json
    success = db.create_leave_request(
        data["employee_id"],
        data["leave_type"],
        data["start_date"],
        data["end_date"],
        data.get("reason", ""),
    )
    return jsonify({"success": success})


@app.route("/api/leave/employee/<int:employee_id>", methods=["GET"])
def get_employee_requests(employee_id):
    requests_list = db.get_requests_for_employee(employee_id)
    return jsonify({"requests": requests_list})


@app.route("/api/leave/pending/<int:approver_id>", methods=["GET"])
def get_pending_requests(approver_id):
    requests_list = db.get_pending_requests_for_approver(approver_id)
    return jsonify({"requests": requests_list})


@app.route("/api/leave/status", methods=["POST"])
def update_status():
    data = request.json
    success = db.update_leave_status(
        data["request_id"],
        data["status"],
        data["decided_by"],
    )
    return jsonify({"success": success})


@app.route("/api/leave/cancel", methods=["POST"])
def cancel_leave():
    """Approver cancels a pending request — restores balance if it was approved."""
    data = request.json
    success = db.cancel_leave_request(
        data["request_id"],
        data["cancelled_by"],
    )
    return jsonify({"success": success})


# ─── Employees ────────────────────────────────────────────────────────────────

@app.route("/api/employee/<int:employee_id>", methods=["GET"])
def get_employee(employee_id):
    employee = db.get_employee_by_id(employee_id)
    return jsonify({"employee": employee})


@app.route("/api/employee/<int:employee_id>/balance", methods=["GET"])
def get_balance(employee_id):
    employee = db.get_employee_by_id(employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    balance = {
        k: v for k, v in employee.items()
        if k.endswith("_leave_balance")
    }
    return jsonify({"balance": balance})


@app.route("/api/employee/<int:employee_id>/reporting-officer", methods=["GET"])
def get_reporting_officer(employee_id):
    officer = db.get_reporting_officer(employee_id)
    return jsonify({"reporting_officer": officer})


@app.route("/api/team/<int:approver_id>/calendar", methods=["GET"])
def get_team_calendar(approver_id):
    leaves = db.get_team_leave_calendar(approver_id)
    return jsonify({"leaves": leaves})


# ─── Holidays ─────────────────────────────────────────────────────────────────

@app.route("/api/holidays", methods=["GET"])
def get_holidays():
    holidays = db.get_holidays()
    return jsonify({"holidays": holidays})


# ─── Chatbot ──────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    import chatbot
    data = request.json
    user = data.get("user", {})
    question = data.get("question", "")
    answer = chatbot.ask_chatbot(user, question)
    return jsonify({"answer": answer})


# ─── Query (text-to-SQL) ──────────────────────────────────────────────────────

@app.route("/api/query", methods=["POST"])
def run_query():
    data = request.json
    result = db.execute_readonly_query(data["sql"])
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)