from pydantic import BaseModel


class TranslateTextRequest(BaseModel):
    text: str
    language: str = "English"