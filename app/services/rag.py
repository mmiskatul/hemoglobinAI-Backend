import hashlib
from openai import AsyncOpenAI
from app.core.config import get_settings


def _client():
    settings = get_settings()
    if not settings.pinecone_api_key or not (settings.pinecone_index_host or settings.pinecone_index_name):
        return None
    from pinecone import Pinecone
    client = Pinecone(api_key=settings.pinecone_api_key)
    return client.Index(host=settings.pinecone_index_host) if settings.pinecone_index_host else client.Index(settings.pinecone_index_name)


async def retrieve_context(query: str, top_k: int = 5) -> list[str]:
    settings = get_settings()
    index = _client()
    if not index or not settings.openai_api_key:
        return []
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        embedding = await client.embeddings.create(model=settings.openai_embedding_model, input=query)
        result = index.query(
            namespace=settings.pinecone_namespace,
            vector=embedding.data[0].embedding,
            top_k=top_k,
            include_metadata=True,
        )
        return [
            str(match.get("metadata", {}).get("text", ""))
            for match in result.get("matches", [])
            if match.get("metadata", {}).get("text")
        ]
    except Exception:
        return []


async def upsert_knowledge(text: str, source: str) -> str:
    settings = get_settings()
    index = _client()
    if not index or not settings.openai_api_key:
        raise RuntimeError("Pinecone and OpenAI embedding configuration is required")
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    embedding = await client.embeddings.create(model=settings.openai_embedding_model, input=text)
    record_id = hashlib.sha256((source + ":" + text).encode("utf-8")).hexdigest()
    index.upsert(
        namespace=settings.pinecone_namespace,
        vectors=[{
            "id": record_id,
            "values": embedding.data[0].embedding,
            "metadata": {"text": text, "source": source},
        }],
    )
    return record_id
