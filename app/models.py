from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


# --- OpenAI /chat/completions ---

class ChatCompletionRequest(BaseModel):
    model: str = "deepseek-v3"
    messages: List[Message]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    # Dangbei-specific extensions
    user_action: Optional[str] = Field(
        default=None,
        description="Comma-separated: 'online', 'deep', 'online,deep'"
    )


# --- OpenAI Response API /v1/response ---

class ResponseInputItem(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ResponseRequest(BaseModel):
    model: str = "deepseek-v3"
    input: List[ResponseInputItem]
    stream: bool = False
    instructions: Optional[str] = None
    # Dangbei-specific extensions
    user_action: Optional[str] = Field(
        default=None,
        description="Comma-separated: 'online', 'deep', 'online,deep'"
    )


# --- Model list ---

class ModelOption(BaseModel):
    title: str
    value: str
    disable: bool
    selected: bool


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "dangbei"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]
