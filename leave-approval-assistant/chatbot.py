import os
import re
import requests
from dotenv import load_dotenv
import db

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"  # adjust to whichever Groq model you have access to

# Schema description given to the LLM so it knows what it can query.
# Keep this in sync with your actual database structure.
SCHEMA_DESCRIPTION = """
Table: employees
- id (INT, primary key)
- name (VARCHAR)
- email (VARCHAR)
- role (ENUM: 'employee', 'approver')
- manager_id (INT, references employees.id)
- sick_leave_balance (INT)
- casual_leave_balance (INT)
- paid_leave_balance (INT)

Table: leave_requests
- id (INT, primary key)
- employee_id (INT, references employees.id)
- leave_type (ENUM: 'sick', 'casual', 'paid')
- start_date (DATE)
- end_date (DATE)
- reason (TEXT)
- status (ENUM: 'pending', 'approved', 'rejected')
- applied_on (TIMESTAMP)
- decided_by (INT, references employees.id)
- decided_on (TIMESTAMP)
"""


def generate_sql(question, approver_id):
    """Asks the LLM to convert a natural language question into a SQL SELECT query,
    scoped to the current approver's team."""
    system_prompt = f"""You are a SQL generator for a leave management system.

Database schema:
{SCHEMA_DESCRIPTION}

Rules:
- Only generate SELECT statements. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
- The current user is an approver with id = {approver_id}.
- If the question refers to a specific employee BY NAME (e.g. "Employee One",
  "John"), you must look that employee up by matching the `name` column
  (e.g. WHERE name = 'Employee One'), NOT by guessing or reusing any id
  number mentioned elsewhere in this prompt. Never assume an employee's id —
  always resolve it via the name column.
- When the question is about which requests/employees an approver manages
  (not about a specific named employee), scope queries to employees where
  manager_id = {approver_id}.
- If the question is about the approver's own data specifically, you may use
  id = {approver_id}.
- Return ONLY the raw SQL query. No explanation, no markdown formatting, no
  backticks, no comments — just the SQL statement itself ending in nothing
  but the query.
"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "max_tokens": 300,
        "temperature": 0,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    raw_sql = data["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if the model added them anyway
    raw_sql = re.sub(r"^```sql\s*|```$", "", raw_sql, flags=re.MULTILINE).strip()
    return raw_sql


def explain_result(question, rows):
    """Sends the query result back to the LLM to phrase a natural-language answer."""
    system_prompt = (
        "You are a helpful assistant for a leave approval system. "
        "Given the user's question and the raw query result (a list of rows), "
        "answer concisely in plain language. If the result is empty, say so clearly."
    )

    user_content = f"Question: {question}\n\nQuery result: {rows}"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 300,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def ask_chatbot(approver_id, question):
    """Main entry point: question -> SQL -> live DB query -> natural language answer."""
    if not GROQ_API_KEY:
        return "GROQ_API_KEY is not set. Add it to your .env file."

    try:
        sql = generate_sql(question, approver_id)
    except requests.exceptions.RequestException as e:
        return f"Error generating query: {e}"

    result = db.execute_readonly_query(sql)

    if "error" in result:
        return f"Couldn't run that query ({result['error']}). Generated SQL was:\n{sql}"

    rows = result["rows"]

    try:
        answer = explain_result(question, rows)
    except requests.exceptions.RequestException:
        # Fall back to showing raw rows if the explanation call fails
        return f"Result: {rows}"

    return answer


if __name__ == "__main__":
    # Quick manual test — replace 1 with a real approver id from your employees table
    test_approver_id = 1
    test_question = "How many pending requests do I have?"
    print(ask_chatbot(test_approver_id, test_question))
