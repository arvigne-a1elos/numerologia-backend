"""Database models and schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from config import get_settings

settings = get_settings()

# Database setup
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# SQLAlchemy Models
# ============================================================================

class Calculation(Base):
    """Numerology calculation database model."""

    __tablename__ = "calculations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    birth_date = Column(String, nullable=False)
    email = Column(String, nullable=True, index=True)
    life_path = Column(Integer, nullable=False)
    expression = Column(Integer, nullable=False)
    soul_urge = Column(Integer, nullable=False)
    personality = Column(Integer, nullable=False)
    destiny = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Calculation(id={self.id}, name={self.name}, email={self.email})>"


# Create all tables
Base.metadata.create_all(bind=engine)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class CalculationCreate(BaseModel):
    """Schema for creating a calculation."""

    name: str = Field(..., min_length=1, max_length=255)
    birth_date: str
    email: Optional[str] = None
    life_path: int
    expression: int
    soul_urge: int
    personality: int
    destiny: int

    class Config:
        json_schema_extra = {
            "example": {
                "name": "João Silva",
                "birth_date": "1990-05-15",
                "email": "joao@example.com",
                "life_path": 7,
                "expression": 5,
                "soul_urge": 3,
                "personality": 2,
                "destiny": 9,
            }
        }


class CalculationResponse(CalculationCreate):
    """Schema for returning a calculation."""

    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentRequest(BaseModel):
    """Schema for payment requests."""

    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(default="")
    product: str = Field(default="pdf8")
    price: float = Field(default=0.0, ge=0)
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: str = Field(default="pt", pattern="^(pt|en|es)$")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "João Silva",
                "email": "joao@example.com",
                "product": "pdf8",
                "price": 29.99,
                "calculation_id": "abc123",
                "birth_date": "1990-05-15",
                "lang": "pt",
            }
        }


class PaymentResponse(BaseModel):
    """Schema for payment response."""

    success: bool
    message: str
    transaction_id: Optional[str] = None
    error: Optional[str] = None
