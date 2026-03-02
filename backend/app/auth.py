"""
Auth dependency: validates NextAuth JWT from Authorization header or cookie
and returns the associated Host from DB.
"""
import logging
from typing import Optional
import uuid

from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models.host import Host

settings = get_settings()
logger = logging.getLogger(__name__)


def _extract_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()
    # Fall back to NextAuth session token cookie
    return request.cookies.get("next-auth.session-token") or request.cookies.get(
        "__Secure-next-auth.session-token"
    )


async def get_current_host(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Host:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token,
            settings.NEXTAUTH_SECRET if hasattr(settings, "NEXTAUTH_SECRET") else "",
            algorithms=["HS256"],
            options={"verify_signature": False},
        )
        google_id: Optional[str] = payload.get("sub") or payload.get("googleId")
        email: Optional[str] = payload.get("email")
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if not google_id and not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing identity claims",
        )

    query = select(Host).where(Host.is_active == True)
    if google_id:
        query = query.where(Host.google_id == google_id)
    elif email:
        query = query.where(Host.email == email)

    result = await db.execute(query)
    host = result.scalar_one_or_none()
    if not host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Host not found",
        )
    return host
