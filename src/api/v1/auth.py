"""
Authentication API endpoints and dependency guards for HostCart.
Handles registration, login, profile retrieval, and JWT role-based access control.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, func, select

from src.api.v1.schemas import TokenResponse, UserLogin, UserRead, UserRegister
from src.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.data.database import get_session
from src.data.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: Session = Depends(get_session),
) -> User:
    """Dependency extracting and validating the JWT Bearer token, returning the User."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency verifying that the authenticated user possesses admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegister,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """
    Register a new user account.
    If this is the very first user in the database, grant admin privileges (is_admin=True).
    """
    # Check if this will be the initial administrator
    total_users = session.exec(select(func.count(User.id))).one()
    is_initial_admin = total_users == 0

    # Ensure uniqueness of username and email (case-insensitive)
    existing_user = session.exec(
        select(User).where(
            (func.lower(User.username) == payload.username.lower())
            | (func.lower(User.email) == payload.email.lower())
        )
    ).first()

    if existing_user:
        if existing_user.username.lower() == payload.username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    user = User(
        username=payload.username.strip(),
        email=payload.email.strip().lower(),
        hashed_password=hash_password(payload.password),
        is_admin=is_initial_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(
        {"sub": str(user.id), "username": user.username, "is_admin": user.is_admin}
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """
    Authenticate a user via JSON payload or OAuth2 form-urlencoded request.
    Returns a signed JWT access token and user metadata.
    """
    content_type = request.headers.get("content-type", "")
    username = ""
    password = ""

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
    else:
        try:
            body = await request.json()
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request body",
            )

    if not username.strip() or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )

    user = session.exec(
        select(User).where(func.lower(User.username) == username.strip().lower())
    ).first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        {"sub": str(user.id), "username": user.username, "is_admin": user.is_admin}
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Retrieve profile and role info for the currently authenticated user."""
    return UserRead.model_validate(current_user)


@router.get("/admin-only", response_model=UserRead)
def admin_only(admin_user: User = Depends(get_admin_user)) -> UserRead:
    """Verify administrator access. Raises 403 if the user is not an administrator."""
    return UserRead.model_validate(admin_user)

