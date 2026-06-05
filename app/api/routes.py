from fastapi import APIRouter

from app.api.v1.accounts import router as accounts_router
from app.api.v1.auth import router as auth_router
from app.api.v1.transactions import router as transactions_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
router.include_router(transactions_router, prefix="/transactions", tags=["transactions"])


@router.get("/ping")
def ping() -> dict:
    return {"pong": True}


api_router = router
