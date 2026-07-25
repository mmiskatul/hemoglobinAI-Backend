# Hemoglobin AI Backend

FastAPI backend for blood-request intake, authenticated dashboards, donor matching, AI conversations, Pinecone RAG, MongoDB persistence, SMTP notifications, and map services.

## Local setup

From this directory:

```bash
copy .env.example .env
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

OpenAPI documentation is available at http://localhost:8000/docs.

## Environment

The real `.env` file is private and must never be committed. Configure:

- MongoDB or MongoDB Atlas
- JWT secret
- OpenAI API and embedding model
- Pinecone API key, host, namespace, and 1536-dimensional cosine index
- Google Maps server key
- SMTP/Gmail App Password

Generate a JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

More detailed setup guidance is in `SETUP.md`.

## Main API areas

- `/api/v1/auth` — registration and login
- `/api/v1/requests` — blood requests and agent request conversations
- `/api/v1/agent/chat` — authenticated dashboard AI chat
- `/api/v1/agent/knowledge` — protected Pinecone knowledge ingestion
- `/api/v1/donors` — donor profile and availability
- `/api/v1/hospitals` — inventory, orders, and broadcasts
- `/api/v1/courier` — dispatch tasks and delivery completion
- `/api/v1/notifications` — notification retrieval and read state
- `/api/v1/simulations` — simulation execution
- `/api/v1/control-room` — courier monitoring and operation logs
- `/api/v1/requester/vitals` — requester health-log persistence

The AI agent is constrained to supplied registry and retrieved knowledge context. It must not diagnose, guarantee availability, or reveal private donor contact details without consent.

## Docker

```bash
docker build -t hemoglobin-ai-backend .
docker run --env-file .env -p 8000:8000 hemoglobin-ai-backend
```

For production, use HTTPS, managed MongoDB, secret management, rate limiting, background jobs for notification retries, audit retention, and clinical/legal review.
