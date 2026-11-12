"""Public API contract. Mirrored in frontend/src/api/types.ts."""

from pydantic import BaseModel, Field, field_validator

DISCLAIMER = (
    "Educational decision-support only. Not medical advice; "
    "verify against current guidelines and clinical judgment."
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("question must contain at least 3 non-space characters")
        return stripped


class Citation(BaseModel):
    source: str
    page: int = Field(description="1-based PDF page number")
    snippet: str
    cited: bool = Field(description="True if the answer explicitly cites this page")


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    corpus: str
    answered_from_context: bool
    disclaimer: str = DISCLAIMER


class HealthResponse(BaseModel):
    status: str
    corpus: str
    indexed_chunks: int
