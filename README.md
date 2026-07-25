# Hemoglobin AI Backend

FastAPI service for blood-request intake, authenticated donor registration, area/geospatial matching, agent conversations, and notifications.

## Run locally

1. Copy .env.example to .env and set MongoDB and JWT values.
2. Add OPENAI_API_KEY only on the backend server. Never expose it to Next.js.
3. Install dependencies: python -m pip install -r requirements.txt
4. Start: uvicorn app.main:app --reload --port 8000
5. API docs: http://localhost:8000/docs

The OpenAI agent is deliberately constrained to registry context supplied by the API. It does not diagnose, promise availability, or disclose contact details before confirmation. The in-memory fallback is used when OPENAI_API_KEY is absent.

Production requirements still include managed MongoDB, HTTPS, a real identity provider/phone verification flow, a job queue for retries, push/SMS provider, rate limiting, audit retention, and clinical/legal review.
# hemoglobinAI-Backend
