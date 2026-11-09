from fastapi import APIRouter

from bachatcheck.api.v1 import compare, funds, health, meta, stocks

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(compare.router)
router.include_router(funds.router)
router.include_router(stocks.router)
router.include_router(meta.router)
