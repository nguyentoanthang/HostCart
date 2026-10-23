"""
Authentication API endpoints and dependency guards for HostCart.
Handles registration, login, profile retrieval, JWT role-based access control,
and dual-mode Homelab SSO / service-to-service OBO authentication.
"""

from __future__ import annotations

import hmac
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, func, select

from src.api.v1.schemas import TokenResponse, UserLogin, UserRead, UserRegister
from src.core.config import get_settings
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


def _decode_sso_token(sso_token: str, sso_secret: str) -> dict:
    """Decode and validate an SSO JWT token using the HS256 secret."""
    if not sso_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired SSO token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return jwt.decode(sso_token, sso_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired SSO token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _process_sso_payload(payload: dict, session: Session) -> User:
    """Verify SSO permissions and JIT-provision or sync local User."""
    is_admin = bool(payload.get("is_admin", False))
    allowed_apps = payload.get("allowed_apps", [])
    if not (is_admin or "hostcart" in allowed_apps):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HostCart access not permitted for this user",
        )

    raw_username = payload.get("username")
    if not raw_username or not str(raw_username).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SSO token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username_clean = str(raw_username).strip()
    raw_email = payload.get("email")
    email = (
        str(raw_email).strip().lower()
        if raw_email
        else f"{username_clean.lower()}@homelab.local"
    )

    user = session.exec(
        select(User).where(func.lower(User.username) == username_clean.lower())
    ).first()

    if not user:
        user = User(
            username=username_clean,
            email=email,
            hashed_password="<sso-managed>",
            is_admin=is_admin,
        )
        session.add(user)
    else:
        user.is_admin = is_admin
        if email and user.email != email:
            user.email = email
        session.add(user)

    session.commit()
    session.refresh(user)
    return user


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: Session = Depends(get_session),
) -> User:
    """
    Dependency extracting and validating credentials, returning the User.
    Supports standalone JWT auth or Homelab SSO / service-to-service OBO auth.
    """
    settings = get_settings()

    if settings.homelab.auth_mode == "homelab":
        # 1. Path A (Service-to-Service OBO headers)
        x_homelab_token = request.headers.get("x-homelab-token") if request else None
        if x_homelab_token is not None:
            internal_token = settings.homelab.homelab_internal_token
            if not internal_token or not hmac.compare_digest(x_homelab_token, internal_token):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid internal service token",
                )
            x_homelab_user = request.headers.get("x-homelab-user")
            if not x_homelab_user or not x_homelab_user.strip():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing X-Homelab-User header",
                )
            username_clean = x_homelab_user.strip()
            raw_admin = request.headers.get("x-homelab-is-admin", "")
            x_homelab_is_admin = raw_admin.lower() in ("true", "1")

            user = session.exec(
                select(User).where(func.lower(User.username) == username_clean.lower())
            ).first()

            if not user:
                user = User(
                    username=username_clean,
                    email=f"{username_clean.lower()}@homelab.local",
                    hashed_password="<sso-managed>",
                    is_admin=x_homelab_is_admin,
                )
                session.add(user)
            else:
                if "x-homelab-is-admin" in request.headers:
                    user.is_admin = x_homelab_is_admin
                session.add(user)

            session.commit()
            session.refresh(user)
            return user

        # 2. Path B (Central SSO JWT)
        cookie_sso = request.cookies.get("homelab_sso") if request else None
        if cookie_sso:
            payload = _decode_sso_token(cookie_sso, settings.homelab.homelab_sso_secret)
            return _process_sso_payload(payload, session)

        header_sso = request.headers.get("x-homelab-sso-token") if request else None
        if header_sso:
            payload = _decode_sso_token(header_sso, settings.homelab.homelab_sso_secret)
            return _process_sso_payload(payload, session)

        if credentials and credentials.credentials:
            bearer_token = credentials.credentials
            # Attempt to decode as SSO token if secret is configured
            if settings.homelab.homelab_sso_secret:
                try:
                    sso_payload = jwt.decode(
                        bearer_token,
                        settings.homelab.homelab_sso_secret,
                        algorithms=["HS256"],
                    )
                    if "username" in sso_payload:
                        return _process_sso_payload(sso_payload, session)
                except HTTPException:
                    raise
                except jwt.PyJWTError:
                    pass

            # 3. Path C (Local HostCart token fallback)
            local_payload = decode_access_token(bearer_token)
            if not local_payload or "sub" not in local_payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired access token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            try:
                user_id = int(local_payload["sub"])
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

        # 4. If none of the above succeed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Standalone mode (AUTH_MODE=standalone)
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
    Disabled when AUTH_MODE is 'homelab'.
    """
    settings = get_settings()
    if settings.homelab.auth_mode == "homelab":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is managed centrally by Homelab Dashboard",
        )

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


@router.get("/sso-session", response_model=TokenResponse)
def sso_session(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: Session = Depends(get_session),
) -> TokenResponse:
    """
    Validate an active Homelab SSO session from cookie, header, or Bearer token.
    In auth_mode == 'homelab', resolves/JIT-provisions the user and returns
    a local TokenResponse for frontend automatic session establishment.
    """
    settings = get_settings()
    if settings.homelab.auth_mode != "homelab":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active Homelab SSO session found",
        )

    # 1. Inspect homelab_sso cookie
    sso_token = request.cookies.get("homelab_sso") if request else None

    # 2. Inspect X-Homelab-SSO-Token header
    if not sso_token and request:
        sso_token = request.headers.get("x-homelab-sso-token")

    # 3. Inspect Authorization: Bearer
    if not sso_token and credentials and credentials.credentials:
        bearer_token = credentials.credentials
        if settings.homelab.homelab_sso_secret:
            try:
                decoded = jwt.decode(
                    bearer_token,
                    settings.homelab.homelab_sso_secret,
                    algorithms=["HS256"],
                )
                if "username" in decoded:
                    sso_token = bearer_token
            except jwt.PyJWTError:
                pass

        if not sso_token:
            local_payload = decode_access_token(bearer_token)
            if local_payload and "sub" in local_payload:
                try:
                    user_id = int(local_payload["sub"])
                    user = session.get(User, user_id)
                    if user:
                        local_token = create_access_token(
                            {
                                "sub": str(user.id),
                                "username": user.username,
                                "is_admin": user.is_admin,
                            }
                        )
                        return TokenResponse(
                            access_token=local_token,
                            token_type="bearer",
                            user=UserRead.model_validate(user),
                        )
                except (ValueError, TypeError):
                    pass

    if not sso_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active Homelab SSO session found",
        )

    try:
        payload = _decode_sso_token(sso_token, settings.homelab.homelab_sso_secret)
        user = _process_sso_payload(payload, session)
    except HTTPException as e:
        if e.status_code == status.HTTP_403_FORBIDDEN:
            raise e
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active Homelab SSO session found",
        )

    local_token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
        }
    )

    return TokenResponse(
        access_token=local_token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )
