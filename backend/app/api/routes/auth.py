"""API route: auth admin — POST /api/auth/login."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import create_token, verify_password
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class LoginResponse(BaseModel):
    token: str
    role: str
    expiresIn: int


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    """Đăng nhập admin bằng mật khẩu → trả token."""
    settings = get_settings()
    if not settings.admin_password_hash:
        raise HTTPException(status_code=400, detail="Auth chưa cấu hình (ADMIN_PASSWORD_HASH trống).")

    if not verify_password(req.password, settings.admin_password_hash):
        # Làm chậm brute-force (~1 req/giây). Production nên đặt sau reverse proxy có rate-limit.
        await asyncio.sleep(1)
        logger.warning("Đăng nhập admin THẤT BẠI (sai mật khẩu).")
        raise HTTPException(status_code=401, detail="Mật khẩu không đúng.")

    logger.info("Đăng nhập admin thành công.")
    return LoginResponse(
        token=create_token(settings.auth_secret_key, settings.auth_token_ttl),
        role="admin",
        expiresIn=settings.auth_token_ttl,
    )
