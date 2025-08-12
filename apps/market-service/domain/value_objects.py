"""Value objects for market-service."""

from pydantic import BaseModel, validator


class Money(BaseModel):
    """Money value object."""

    amount: float
    currency: str = "USD"

    class Config:
        frozen = True

    @validator("amount")
    def amount_must_be_positive(cls, v):
        if v < 0:
            raise ValueError("Amount must be positive")
        return v


class Email(BaseModel):
    """Email value object."""

    value: str

    class Config:
        frozen = True

    @validator("value")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class Address(BaseModel):
    """Address value object."""

    street: str
    city: str
    country: str
    postal_code: str

    class Config:
        frozen = True
