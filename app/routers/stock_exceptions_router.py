from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.stock_exceptions import StockException, StockExceptionCreate
from app.models.stock_exceptions import StockException as StockExceptionModel
from app.database import get_db

router = APIRouter()

@router.post("/exceptions/", response_model=StockException)
def create_exception(exception: StockExceptionCreate, db: Session = Depends(get_db)):
    db_exception = StockExceptionModel(**exception.model_dump())
    db.add(db_exception)
    db.commit()
    db.refresh(db_exception)
    return db_exception