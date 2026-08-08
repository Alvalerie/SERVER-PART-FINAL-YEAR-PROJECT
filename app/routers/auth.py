from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..dependencies.auth import get_current_user
from ..dependencies.database import get_db
from ..models.user_model import User
from ..schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
)
from ..services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    """
    Authenticate with email and password.

    Returns:
    - **access_token** — short-lived (30 min). Send as `Authorization: Bearer <token>`.
    - **refresh_token** — long-lived (7 days). Store securely; use on `/refresh`.
    """
    return service.login(payload)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    """
    Exchange a valid refresh token for a new access token.

    - The old refresh token is **revoked** (token rotation).
    - A new refresh token is issued alongside the new access token.
    - If a revoked token is reused, **all sessions are immediately revoked**
      as a security measure against token theft.
    """
    return service.refresh(payload)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, service: AuthService = Depends(get_auth_service)):
    """
    Revoke the provided refresh token.
    The access token expires naturally — store it short-lived (30 min).
    """
    return service.logout(payload)


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke ALL refresh tokens for the authenticated user.
    Logs out every device simultaneously. Requires a valid access token.
    """
    return service.logout_all(current_user.id)