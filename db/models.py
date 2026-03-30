from pydantic import BaseModel, Field

# TEMPORARY - Dev 3 will replace this


class DocumentResponse(BaseModel):
    file_bytes: bytes
    filename: str
    caption: str = ""


class HandlerResponse(BaseModel):
    messages: list[str] = Field(default_factory=list)
    documents: list[DocumentResponse] | None = None
