import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are an AI assistant for a leave management system.
Your job is to understand the user's query and return a structured JSON response.

Always return ONLY a valid JSON object in this exact universal schema:
{
  "intent": "<INTENT>",
  "module": "LEAVE",
  "employee": {
    "empCode": null,
    "empName": "<name if mentioned, else null>"
  },
  "leave": {
    "leaveType": "<slug if mentioned, else null>",
    "fromDate": "<YYYY-MM-DD if mentioned, else null>",
    "toDate": "<YYYY-MM-DD if mentioned, else null>",
    "days": <number if calculable, else null>,
    "reason": "<reason if mentioned, else null>",
    "status": "<pending/approved/rejected if mentioned, else null>"
  },
  "filters": {},
  "context": {
    "role": "<EMPLOYEE or MANAGER>"
  },
  "confidence": <0.0 to 1.0>
}

Available intents:
- GET_LEAVE_BALANCE       → user asks about remaining leave days for a type
- GET_ALL_LEAVE_BALANCE   → user asks for all leave balances
- GET_PENDING_LEAVES      → user asks for their pending leave applications
- GET_LEAVE_HISTORY       → user asks for past leave records
- APPLY_LEAVE             → user wants to apply for leave
- CANCEL_LEAVE            → user wants to cancel a leave
- GET_LEAVE_STATUS        → user asks status of a specific leave request
- GET_REPORTING_OFFICER   → user asks who their manager/reporting officer is
- GET_HOLIDAYS            → user asks about holidays
- GET_PENDING_APPROVALS   → manager asks about pending approvals from their team
- LEAVE_POLICY            → user asks about leave rules or policies

Leave type slugs (map abbreviations to these):
- annual (EL, Earned Leave, Annual Leave)
- casual (CL, Casual Leave)
- sick (SL, Sick Leave, Medical Leave)
- paid (PL, Paid Leave)
- comp-off (Comp Off, Compensatory Off)
- wfh (WFH, Work From Home)
- maternity (ML, Maternity Leave)
- paternity (Paternity Leave)
- bereavement (Bereavement Leave)
- lwp (LWP, Loss of Pay, Unpaid Leave)
- emergency (Emergency Leave)
- study (Study Leave)
- sabbatical (Sabbatical Leave)
- marriage (Marriage Leave)
- half-day (Half Day)
- holiday (Optional Holiday)

Rules:
- Return ONLY the JSON object. No explanation, no markdown, no backticks.
- If the user mentions a specific employee name, put it in empName.
- If the user asks about themselves (no name mentioned), leave empName as null.
- Map all leave abbreviations to the correct slug.
- Calculate days from fromDate and toDate if both are provided.
- For GET_PENDING_APPROVALS, set context.role to MANAGER.
- confidence should reflect how certain you are about the intent (0.0 to 1.0).
- "Employee 3", "Employee 5" etc. are full employee names, not codes.
  Always put the full string (e.g. "Employee 3") into empName, never split
  the number into empCode. empCode is only for alphanumeric codes like "EMP001".
"""


def parse_intent(question):
    """Send question to LLM and get back structured intent JSON."""
    if not GROQ_API_KEY:
        return {"error": "GROQ_API_KEY not set"}

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "max_tokens": 400,
        "temperature": 0,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if model added them anyway
        raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)

    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        return {"error": str(e)}


def resolve_intent(intent_json, user):
    """Takes the parsed intent JSON and the logged-in user,
    calls the right db function, and returns a natural language answer."""
    import db

    intent = intent_json.get("intent")
    emp = intent_json.get("employee", {})
    leave = intent_json.get("leave", {})
    filters = intent_json.get("filters", {})

    # Resolve employee — if empName is mentioned, look them up
    # otherwise default to the logged-in user
    target_employee = None
    emp_name = emp.get("empName")
    emp_code = emp.get("empCode")

    if emp_name:
        target_employee = db.get_employee_by_name(emp_name)
        if not target_employee:
            return f"I couldn't find an employee named '{emp_name}'."
    elif emp_code and emp_code.isdigit() is False:
        # Alphanumeric code like EMP001 — look up by id or code
        target_employee = user
    else:
        target_employee = user

    emp_id = target_employee["id"]
    emp_name = target_employee["name"]

    # ── Handle each intent ──────────────────────────────────────────────────

    if intent == "GET_LEAVE_BALANCE":
        leave_type = leave.get("leaveType")
        emp_data = db.get_employee_by_id(emp_id)
        if not leave_type:
            return "Please specify which type of leave balance you want to check."
        from leave_types import LEAVE_TYPES
        lt = next((l for l in LEAVE_TYPES if l["slug"] == leave_type), None)
        if not lt:
            return f"Unknown leave type: {leave_type}"
        balance = emp_data.get(lt["column"], 0)
        return f"{emp_name} has {balance} {lt['display']} days remaining."

    elif intent == "GET_ALL_LEAVE_BALANCE":
        emp_data = db.get_employee_by_id(emp_id)
        from leave_types import LEAVE_TYPES
        lines = [f"{lt['display']}: {emp_data.get(lt['column'], 0)} days" for lt in LEAVE_TYPES]
        return f"Leave balances for {emp_name}:\n" + "\n".join(lines)

    elif intent == "GET_PENDING_LEAVES":
        requests_list = db.get_requests_for_employee(emp_id)
        pending = [r for r in requests_list if r["status"] == "pending"]
        if not pending:
            return f"{emp_name} has no pending leave applications."
        lines = [f"- {r['leave_type']} from {str(r['start_date'])[:10]} to {str(r['end_date'])[:10]}" for r in pending]
        return f"{emp_name} has {len(pending)} pending leave(s):\n" + "\n".join(lines)

    elif intent == "GET_LEAVE_HISTORY":
        limit = filters.get("limit", 10)
        requests_list = db.get_requests_for_employee(emp_id)[:limit]
        if not requests_list:
            return f"{emp_name} has no leave history."
        lines = [f"- {r['leave_type']} | {str(r['start_date'])[:10]} to {str(r['end_date'])[:10]} | {r['status']}" for r in requests_list]
        return f"Last {len(requests_list)} leave(s) for {emp_name}:\n" + "\n".join(lines)

    elif intent == "GET_REPORTING_OFFICER":
        officer = db.get_reporting_officer(emp_id)
        if not officer:
            return f"{emp_name} has no reporting officer assigned."
        return f"{emp_name}'s reporting officer is {officer['name']} ({officer['email']})."

    elif intent == "GET_PENDING_APPROVALS":
        approver_id = user["id"]
        pending = db.get_pending_requests_for_approver(approver_id)
        if not pending:
            return "You have no pending leave approvals."
        lines = [f"- {r['employee_name']}: {r['leave_type']} from {str(r['start_date'])[:10]} to {str(r['end_date'])[:10]}" for r in pending]
        return f"You have {len(pending)} pending approval(s):\n" + "\n".join(lines)

    elif intent == "GET_HOLIDAYS":
        holidays = db.get_holidays()
        month = filters.get("month")
        if month:
            holidays = [h for h in holidays if int(str(h["date"])[5:7]) == month]
        if not holidays:
            return "No holidays found for the specified period."
        lines = [f"- {h['name']}: {str(h['date'])[:10]} ({h['type']})" for h in holidays]
        return "Holidays:\n" + "\n".join(lines)

    elif intent == "LEAVE_POLICY":
        leave_types_mentioned = leave.get("leaveType", [])
        if isinstance(leave_types_mentioned, str):
            leave_types_mentioned = [leave_types_mentioned]
        types_str = ", ".join(leave_types_mentioned) if leave_types_mentioned else "the requested leave type"
        return (
            f"Leave policy for {types_str}: Please refer to the company leave policy document. "
            f"For specific queries, contact HR or your reporting officer."
        )

    elif intent == "GET_LEAVE_STATUS":
        requests_list = db.get_requests_for_employee(emp_id)
        if not requests_list:
            return f"{emp_name} has no leave requests."
        latest = requests_list[0]
        return (
            f"Latest leave request for {emp_name}: "
            f"{latest['leave_type']} from {str(latest['start_date'])[:10]} to {str(latest['end_date'])[:10]} "
            f"— Status: {latest['status'].upper()}"
        )

    elif intent == "APPLY_LEAVE":
        return (
            f"To apply leave, please use the 'Apply Leave' tab on your dashboard. "
            f"Details extracted: Type={leave.get('leaveType')}, "
            f"From={leave.get('fromDate')}, To={leave.get('toDate')}, "
            f"Reason={leave.get('reason')}"
        )

    elif intent == "CANCEL_LEAVE":
        return (
            f"To cancel a leave, please use the 'My Requests' tab and click Cancel. "
            f"Leave starting {leave.get('fromDate')} will be cancelled."
        )

    else:
        return f"I understood your request (intent: {intent}) but couldn't process it automatically. Please use the dashboard."


def ask_chatbot(user, question):
    """Main entry point: question + logged-in user → intent → answer."""
    intent_json = parse_intent(question)

    if "error" in intent_json:
        return f"Error parsing your request: {intent_json['error']}"

    answer = resolve_intent(intent_json, user)
    return answer


if __name__ == "__main__":
    # Quick test
    test_user = {"id": 1, "name": "Approver One", "role": "approver"}
    print(ask_chatbot(test_user, "How many CL leaves do I have?"))
