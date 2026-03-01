"""FastAPI dependencies"""

import logging
from collections.abc import Awaitable, Callable, Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from pypsa_app.backend.auth.session import get_session_store
from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.models import Network, Permission, User
from pypsa_app.backend.permissions import can_access_network, has_permission
from pypsa_app.backend.settings import SESSION_COOKIE_NAME, settings

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session]:
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Return authenticated user or None, never blocking requests."""
    if not settings.enable_auth:
        return None

    # Get session cookie
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        logger.debug("No session cookie found")
        return None

    # Get user_id from session
    try:
        session_store = get_session_store()
        user_id = session_store.get_session(session_id)

        if not user_id:
            logger.debug("Session not found or expired")
            return None

        # Load user from database
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            logger.warning("Session references non-existent user: %s", user_id)
            return None

    except (ConnectionError, OSError) as e:
        logger.exception("Session store connection error")
        raise HTTPException(
            status_code=503,
            detail="Authentication service temporarily unavailable. Please try again.",
        ) from e

    logger.debug("User authenticated: %s (role: %s)", user.username, user.role)
    return user


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    """Require authentication when enabled, raising 401 if unauthenticated."""
    if settings.enable_auth and user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in.",
        )

    return user


def require_permission(
    permission: Permission,
) -> Callable[..., Awaitable[User]]:
    """Require a specific permission for the endpoint."""

    async def checker(
        user: User | None = Depends(get_current_user_optional),
    ) -> User:
        # When auth is disabled, allow access
        if not settings.enable_auth:
            return user

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please log in.",
            )

        if not has_permission(user, permission):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to perform this action.",
            )

        return user

    return checker


def get_network_or_404(
    network_id: UUID = Path(..., description="Network UUID"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> Network:
    """Fetch network by ID with access control.

    Raises 404 if not found or inaccessible.
    """
    network = db.query(Network).filter(Network.id == str(network_id)).first()
    if not network:
        raise HTTPException(404, "Network not found")

    if settings.enable_auth and not can_access_network(user, network):
        raise HTTPException(404, "Network not found")

    return network


def get_networks_or_404(
    db: Session,
    network_ids: list[str],
    user: User | None = None,
) -> list[Network]:
    """Validate network_ids exist and user has access. Raises 404 if not."""
    networks = db.query(Network).filter(Network.id.in_(network_ids)).all()

    if len(networks) != len(network_ids):
        raise HTTPException(404, "One or more networks not found")

    if settings.enable_auth:
        for network in networks:
            if not can_access_network(user, network):
                raise HTTPException(404, "One or more networks not found")

    return networks


__all__ = [
    "get_db",
    "get_network_or_404",
    "get_networks_or_404",
    "get_current_user_optional",
    "get_current_user",
    "require_permission",
    "Permission",
]
