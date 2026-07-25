from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    dashboard: str = Field(default="general", max_length=80)
    conversation_id: str | None = None


class KnowledgeUpsertRequest(BaseModel):
    text: str = Field(min_length=20, max_length=20000)
    source: str = Field(min_length=2, max_length=300)
