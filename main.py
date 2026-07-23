"""Main FastAPI application for Numerologia Backend."""

import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import get_settings
from models import (
    Calculation,
    SessionLocal,
    PaymentRequest,
    PaymentResponse,
    CalculationResponse,
    CalculationCreate,
)
from styles import ColorPalette, Typography, ParagraphStyles

# ============================================================================
# Configuration & Logging
# ============================================================================

settings = get_settings()

# Configure logging with better formatting
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="Numerologia API",
    description="API para cálculos e geração de relatórios numerológicos",
    version="1.0.0",
)

# Configure CORS with specific origins (security improvement)
allowed_origins = (
    settings.allowed_origins 
    if isinstance(settings.allowed_origins, list) 
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# ============================================================================
# Dependency Injections
# ============================================================================

def get_db():
    """Dependency to inject database session into endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    logger.error(f"Value Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid input data", "error": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


# ============================================================================
# Calculation Endpoints (Example endpoints - extend as needed)
# ============================================================================

@app.post("/calculations", response_model=CalculationResponse, tags=["Calculations"])
async def create_calculation(
    calculation: CalculationCreate,
    db: Session = Depends(get_db),
):
    """Create a new numerology calculation."""
    try:
        import uuid
        
        calc_id = str(uuid.uuid4())
        db_calculation = Calculation(
            id=calc_id,
            name=calculation.name,
            birth_date=calculation.birth_date,
            email=calculation.email,
            life_path=calculation.life_path,
            expression=calculation.expression,
            soul_urge=calculation.soul_urge,
            personality=calculation.personality,
            destiny=calculation.destiny,
        )
        db.add(db_calculation)
        db.commit()
        db.refresh(db_calculation)
        
        logger.info(f"Created calculation with ID: {calc_id}")
        return db_calculation
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating calculation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating calculation")


@app.get("/calculations/{calculation_id}", response_model=CalculationResponse, tags=["Calculations"])
async def get_calculation(
    calculation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a calculation by ID."""
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()
    
    if not calculation:
        logger.warning(f"Calculation not found: {calculation_id}")
        raise HTTPException(status_code=404, detail="Calculation not found")
    
    return calculation


# ============================================================================
# Payment Endpoints (Example endpoints - extend as needed)
# ============================================================================

@app.post("/payments", response_model=PaymentResponse, tags=["Payments"])
async def create_payment(payment_request: PaymentRequest):
    """Process a payment request."""
    try:
        # Validate payment data
        if not payment_request.name:
            raise ValueError("Name is required")
        
        if payment_request.price < 0:
            raise ValueError("Price cannot be negative")
        
        if payment_request.lang not in ["pt", "en", "es"]:
            raise ValueError("Invalid language")
        
        logger.info(
            f"Processing payment for {payment_request.name} - "
            f"Product: {payment_request.product}, Price: {payment_request.price}"
        )
        
        # TODO: Integrate with Stripe using settings.stripe_secret_key
        
        return PaymentResponse(
            success=True,
            message="Payment processed successfully",
            transaction_id="txn_" + str(datetime.utcnow().timestamp()),
        )
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Payment processing error: {str(e)}", exc_info=True)
        return PaymentResponse(
            success=False,
            message="Payment processing failed",
            error=str(e),
        )


# ============================================================================
# Startup Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Application starting up...")
    logger.info(f"Environment: {settings.base_url}")
    logger.info(f"Database: {settings.database_url}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Application shutting down...")


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Numerologia API",
        "version": "1.0.0",
        "description": "API para cálculos e geração de relatórios numerológicos",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.log_level.lower(),
    )
