from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.user_model import User
from ..repositories.refresh_token import RefreshTokenRepository
from ..schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
)
from ..utils.helpers import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)


class AuthService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.token_repo = RefreshTokenRepository(db)

    def _get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def _get_user_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def login(self, payload: LoginRequest) -> TokenResponse:
        """
        Validate credentials, store the refresh token in the DB,
        and return both tokens.
        """
        user = self._get_user_by_email(payload.email)

        if not user or not verify_password(payload.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(user.id)
        refresh_token_str, expires_at = create_refresh_token(user.id)

        # Persist the refresh token
        self.token_repo.create(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=expires_at,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
        )

    def refresh(self, payload: RefreshRequest) -> AccessTokenResponse:
        """
        Validate the refresh token against the DB, revoke it (rotation),
        issue a new refresh token and a new access token.
        """
        user_id = decode_refresh_token(payload.refresh_token)

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check token exists in DB and is not revoked
        stored = self.token_repo.get_by_token(payload.refresh_token)

        if not stored:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not recognised",
            )

        if stored.is_revoked:
            # Possible token reuse attack — revoke ALL tokens for this user
            self.token_repo.revoke_all_for_user(stored.user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has already been used. All sessions have been revoked.",
            )

        if stored.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please log in again.",
            )

        user = self._get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User no longer exists",
            )

        # Rotate — revoke old token, issue new one
        self.token_repo.revoke(stored)
        new_refresh_token_str, new_expires_at = create_refresh_token(user.id)
        self.token_repo.create(
            user_id=user.id,
            token=new_refresh_token_str,
            expires_at=new_expires_at,
        )

        return AccessTokenResponse(
            access_token=create_access_token(user.id),
        )

    def logout(self, payload: LogoutRequest) -> MessageResponse:
        """
        Revoke the provided refresh token so it can no longer be used.
        The access token will expire naturally on its own.
        """
        stored = self.token_repo.get_by_token(payload.refresh_token)

        if not stored or stored.is_revoked:
            # Return success anyway — don't leak whether token existed
            return MessageResponse(message="Logged out successfully")

        self.token_repo.revoke(stored)
        return MessageResponse(message="Logged out successfully")

    def logout_all(self, user_id: int) -> MessageResponse:
        """Revoke all refresh tokens for a user — logs out every device."""
        self.token_repo.revoke_all_for_user(user_id)
        return MessageResponse(message="Logged out from all devices successfully")