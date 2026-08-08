from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..models.refresh_token_model import RefreshToken


class RefreshTokenRepository:
    """
    Handles all direct database interactions for RefreshToken.
    No business logic lives here — only queries and mutations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: int, token: str, expires_at: datetime) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
            is_revoked=False,
        )
        self.db.add(refresh_token)
        self.db.commit()
        self.db.refresh(refresh_token)
        return refresh_token

    def get_by_token(self, token: str) -> RefreshToken | None:
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token == token)
            .first()
        )

    def revoke(self, refresh_token: RefreshToken) -> None:
        """Mark a single token as revoked."""
        refresh_token.is_revoked = True
        self.db.commit()

    def revoke_all_for_user(self, user_id: int) -> None:
        """Revoke every active token for a user — used on logout all / compromise."""
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        ).update({"is_revoked": True})
        self.db.commit()

    def delete_expired(self) -> int:
        """
        Hard-delete tokens that are both expired and revoked.
        Call this periodically (e.g. a scheduled job) to keep the table lean.
        Returns the number of rows deleted.
        """
        now = datetime.now(UTC)
        deleted = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.expires_at < now,
                RefreshToken.is_revoked == True,  # noqa: E712
            )
            .delete()
        )
        self.db.commit()
        return deleted