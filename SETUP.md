# Backend setup

Run all commands from the backend directory.

## 1. Create the private environment file

PowerShell:

    Copy-Item .env.example .env

Linux/macOS:

    cp .env.example .env

Edit .env and add the real MongoDB, OpenAI, Pinecone, Google Maps, JWT, and SMTP values.

## 2. Generate a JWT secret

    python -c "import secrets; print(secrets.token_urlsafe(48))"

Copy the output into JWT_SECRET_KEY.

## 3. Install dependencies

    python -m pip install -r requirements.txt

Pinecone is included in requirements.txt. Do not put API keys in Python source code.

## 4. Start the API

    uvicorn app.main:app --reload --port 8000

OpenAPI documentation:

    http://localhost:8000/docs

## 5. Pinecone index

Use an index with:

- Dimension: 1536
- Metric: cosine
- Namespace: hemoglobin-knowledge

Set either PINECONE_INDEX_HOST or PINECONE_INDEX_NAME in .env. The host is preferred when available.

## Secret handling

- backend/.env is private and ignored by Git.
- backend/.env.example contains no secrets.
- Rotate any key that has been exposed publicly.
