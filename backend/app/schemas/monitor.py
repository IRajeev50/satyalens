from pydantic import BaseModel, Field
class MonitorCreate(BaseModel):
    query: str = Field(min_length=3,max_length=1000)
    language: str = Field(default="en",pattern="^(en|hi)$")
