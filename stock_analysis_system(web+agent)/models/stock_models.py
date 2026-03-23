from pydantic import BaseModel, Field, field_validator

from models.market import normalize_market_to_cn


class AnalyzeRequest(BaseModel):
    stock_code: str = Field(..., description="股票代码")
    market: str = Field(
        ...,
        description='市场：中文「美股」「A股」「港股」或英文 US/CN/HK',
        examples=["美股", "A股", "港股"],
    )
    days: int = Field(30, ge=1, le=365, description="历史天数")

    @field_validator("market", mode="before")
    @classmethod
    def _normalize_market(cls, v):
        if v is None:
            return v
        return normalize_market_to_cn(str(v))


class SimpleAnalyzeRequest(BaseModel):
    stock_code: str = Field(...)
    market: str = Field(
        ...,
        description="美股 / A股 / 港股（或 US / CN / HK）",
        examples=["港股"],
    )
    days: int = Field(30, ge=1, le=365)

    @field_validator("market", mode="before")
    @classmethod
    def _normalize_market(cls, v):
        if v is None:
            return v
        return normalize_market_to_cn(str(v))
