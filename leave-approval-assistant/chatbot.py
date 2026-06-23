import os
import requests
from dotenv import load_dotenv
import db

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"  # adjust to whichever Groq model you have access to


def build_context_for_approver(approver_id):
    """Pulls pending requests for this approver and turns them into readable text
    the LLM can use as context."""
    pending = db.get_pending_requests_for_approver(approver_id)

    if not pending:
        return "There are no pending leave requests right now."

    lines = []
    for req in pending:
        lines.append(
            f"- Request #{req['id']}: {req['employee_name']} requested "
            f"{req['leave_type']} leave from {req['start_date']} to {req['end_date']} "
            f"(reason: {req['reason']})."
        )
    return "\n".join(lines)


def ask_chatbot(approver_id, question):
    """Sends the approver's question + relevant leave data to Groq and returns the answer."""
    if not GROQ_API_KEY:
        return "GROQ_API_KEY is not set. Add it to your .env file."

    context = build_context_for_approver(approver_id)

    system_prompt = (
        "You are a helpful assistant for a leave approval system. "
        "Use the pending leave request data below to answer the approver's question. "
        "Be concise and only reference the data provided.\n\n"
        f"Pending leave requests:\n{context}"
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "max_tokens": 500,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return f"Error reaching the chatbot service: {e}"


if __name__ == "__main__":
    # Quick manual test — replace 1 with a real approver id from your employees table
    test_approver_id = 1
    test_question = "How many pending requests do I have?"
    print(ask_chatbot(test_approver_id, test_question))
