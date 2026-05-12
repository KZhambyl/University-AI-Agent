from pydantic import BaseModel, Field

class CountryListOutput(BaseModel):
    countries: list[str] = Field(description="List of country names in English")
    reasoning: str = Field(description="Why these countries match the user's description")

class UniversitySearchInput(BaseModel):
    country: str = Field(description="Country name in English, e.g. 'Spain'")
    limit: int = Field(default=3, description="How many universities to return")

class CurrencyConversionInput(BaseModel):
    country: str = Field(description="Country name in English")
    amount_local: float = Field(default=1, description="Amount in local currency to convert (default: 1)")

class CurrencyRateInput(BaseModel):
    country: str = Field(description="Country name in English, e.g. 'Germany'")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False