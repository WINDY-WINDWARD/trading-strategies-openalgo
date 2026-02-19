from pydantic import BaseModel


class TickerData(BaseModel):
    ticker: str
    sector: str | None = None
    company_name: str | None = None
    exchange: str | None = None
