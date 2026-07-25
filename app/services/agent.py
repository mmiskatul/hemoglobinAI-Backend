import json
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.services.rag import retrieve_context


async def respond_to_request(request: dict, donors: list[dict], message: str) -> str:
    settings = get_settings()
    fallback = (
        f"I received your {request['blood_type']} request in {request['area']}. "
        f"I found {len(donors)} verified matching donor(s). I will not share contact details "
        "until the requester and donor both confirm consent."
    )
    if not settings.openai_api_key:
        return fallback

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    context = json.dumps({
        "request": {key: request.get(key) for key in ("blood_type", "units", "urgency", "hospital", "area", "details")},
        "donors": [{key: donor.get(key) for key in ("id", "name", "blood_type", "area", "available", "last_verified_at")} for donor in donors],
    })
    response = await client.responses.create(
        model=settings.openai_model,
        instructions=(
            "You are a blood logistics coordination agent. Use only the supplied registry context. "
            "Never diagnose, promise availability, expose phone numbers, or replace emergency services. "
            "State the next verification or consent step briefly."
        ),
        input=f"Registry context: {context}\nRequester message: {message}",
        max_output_tokens=300,
    )
    return response.output_text.strip() or fallback


async def respond_to_dashboard(message: str, dashboard: str, user: dict, history: list[dict], use_knowledge: bool = True) -> str:
    settings = get_settings()
    fallback = (
        f"I'm the Hemoglobin AI coordination agent for the {dashboard} dashboard. "
        "I can help with requests, donors, hospital inventory, courier dispatch, notifications, "
        "and ledger workflows. For emergencies, contact the hospital emergency desk immediately. "
        "Please tell me what you need."
    )
    if not settings.openai_api_key:
        return fallback

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    knowledge = await retrieve_context(message) if use_knowledge else []
    safe_history = [{"role": item["role"], "content": item["content"]} for item in history[-12:]]
    response = await client.responses.create(
        model=settings.openai_model,
        instructions=(
            "You are Hemoglobin AI's dashboard assistant. Help users navigate blood logistics workflows. "
            "Use only the information provided in the conversation and retrieved knowledge. "
            "Never diagnose, guarantee blood availability, reveal private donor contact details, or "
            "take irreversible medical actions. Ask for confirmation before sending notifications or "
            "sharing personal information. Keep answers concise and actionable."
        ),
        input=[
            {"role": "user", "content": f"Dashboard: {dashboard}; User role: {user.get('role', 'unknown')}"},
            {"role": "user", "content": "Retrieved knowledge:\n" + "\n---\n".join(knowledge)},
            *safe_history,
            {"role": "user", "content": message},
        ],
        max_output_tokens=500,
    )
    return response.output_text.strip() or fallback
