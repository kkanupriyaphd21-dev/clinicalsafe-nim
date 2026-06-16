"""Single-table NIM summarization routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.generation.nim_generator import NIMGenerator
from src.models.database import get_db
from src.models.schemas import SummarizeRequest, SummarizeResponse

router = APIRouter(prefix="/summarize", tags=["Summarization"])


@router.post("", response_model=SummarizeResponse)
async def summarize_table(
    request: SummarizeRequest,
    db: Session = Depends(get_db),
):
    try:
        generator = NIMGenerator(db, model=request.model)
        result = generator.generate(
            table_text=request.table_text,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        return SummarizeResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
