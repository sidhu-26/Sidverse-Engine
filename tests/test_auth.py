from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.config import get_settings
from app.core.security import hash_session_token, verify_password
from app.models.session import UserSession
from app.models.user import User

settings = get_settings()


@pytest.mark.asyncio
async def test_successful_registration(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test user registration creates user with Argon2id hash and sets HttpOnly session cookie."""
    payload = {
        "email": "alex@example.com",
        "display_name": "Alex Mercer",
        "password": "SecurePassword123!",
        "timezone": "Asia/Kolkata",
    }
    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert "user" in data
    user_data = data["user"]
    assert user_data["email"] == "alex@example.com"
    assert user_data["display_name"] == "Alex Mercer"
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # Verify session cookie was set
    assert settings.SESSION_COOKIE_NAME in response.cookies

    # Verify database record has valid Argon2id hash
    stmt = select(User).where(User.email == "alex@example.com")
    db_user = (await db_session.execute(stmt)).scalar_one()
    assert db_user.password_hash != "SecurePassword123!"
    assert verify_password("SecurePassword123!", db_user.password_hash)


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected(async_client: AsyncClient) -> None:
    """Test registering with an existing email returns 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "display_name": "Original User",
        "password": "Password123",
    }
    r1 = await async_client.post("/api/auth/register", json=payload)
    assert r1.status_code == status.HTTP_201_CREATED

    # Second attempt with same email
    payload2 = {
        "email": "DUPLICATE@example.com",
        "display_name": "Duplicate User",
        "password": "AnotherPassword456",
    }
    r2 = await async_client.post("/api/auth/register", json=payload2)
    assert r2.status_code == status.HTTP_409_CONFLICT
    assert r2.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_registration_validation_errors(async_client: AsyncClient) -> None:
    """Test validation errors for invalid email and weak passwords."""
    # Invalid email
    r1 = await async_client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "display_name": "Invalid", "password": "Password123"},
    )
    assert r1.status_code == 422

    # Password too short
    r2 = await async_client.post(
        "/api/auth/register",
        json={"email": "valid@example.com", "display_name": "Short", "password": "Pass1"},
    )
    assert r2.status_code == 422

    # Password without digits
    r3 = await async_client.post(
        "/api/auth/register",
        json={"email": "valid@example.com", "display_name": "NoDigit", "password": "PasswordOnly"},
    )
    assert r3.status_code == 422


@pytest.mark.asyncio
async def test_email_normalization(async_client: AsyncClient) -> None:
    """Test that emails with whitespace and mixed cases are normalized properly."""
    payload = {
        "email": "  Normalized.User@Example.COM  ",
        "display_name": "Normalized User",
        "password": "Password123!",
    }
    res = await async_client.post("/api/auth/register", json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["user"]["email"] == "normalized.user@example.com"

    # Login with different casing/whitespace works
    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "NORMALIZED.USER@EXAMPLE.COM", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_login_success_and_failures(async_client: AsyncClient) -> None:
    """Test valid login, invalid password, and unknown email."""
    await async_client.post(
        "/api/auth/register",
        json={"email": "tester@example.com", "display_name": "Tester", "password": "SecretPass123"},
    )

    # 1. Valid login
    r_valid = await async_client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": "SecretPass123"},
    )
    assert r_valid.status_code == status.HTTP_200_OK
    assert settings.SESSION_COOKIE_NAME in r_valid.cookies

    # 2. Invalid password
    r_bad_pw = await async_client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": "WrongPassword123"},
    )
    assert r_bad_pw.status_code == status.HTTP_401_UNAUTHORIZED
    assert r_bad_pw.json()["error"]["message"] == "Invalid email or password."

    # 3. Unknown email
    r_unknown = await async_client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "SecretPass123"},
    )
    assert r_unknown.status_code == status.HTTP_401_UNAUTHORIZED
    assert r_unknown.json()["error"]["message"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_current_user_me_endpoint(async_client: AsyncClient) -> None:
    """Test /api/auth/me authentication verification and profile payload."""
    # Unauthenticated request -> 401
    r_unauth = await async_client.get("/api/auth/me")
    assert r_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # Register and authenticate
    reg_res = await async_client.post(
        "/api/auth/register",
        json={
            "email": "me_test@example.com",
            "display_name": "Me Tester",
            "password": "Pass123456",
        },
    )
    session_cookie = reg_res.cookies[settings.SESSION_COOKIE_NAME]

    # Authenticated via cookie -> 200
    r_me = await async_client.get(
        "/api/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: session_cookie},
    )
    assert r_me.status_code == status.HTTP_200_OK
    data = r_me.json()
    assert data["email"] == "me_test@example.com"
    assert data["display_name"] == "Me Tester"
    assert "password" not in data
    assert "password_hash" not in data

    # Authenticated via Authorization: Bearer header -> 200
    r_bearer = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {session_cookie}"},
    )
    assert r_bearer.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_logout_and_session_invalidation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that logging out revokes the session and clears authentication cookies."""
    reg_res = await async_client.post(
        "/api/auth/register",
        json={
            "email": "logout_test@example.com",
            "display_name": "Logout Tester",
            "password": "Pass123456",
        },
    )
    session_cookie = reg_res.cookies[settings.SESSION_COOKIE_NAME]

    # Logout
    logout_res = await async_client.post(
        "/api/auth/logout",
        cookies={settings.SESSION_COOKIE_NAME: session_cookie},
    )
    assert logout_res.status_code == status.HTTP_200_OK

    # Subsequent /api/auth/me with revoked token must fail with 401
    me_after = await async_client.get(
        "/api/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: session_cookie},
    )
    assert me_after.status_code == status.HTTP_401_UNAUTHORIZED

    # Verify in DB that session is marked is_revoked = True
    token_hash = hash_session_token(session_cookie)
    stmt = select(UserSession).where(UserSession.session_token_hash == token_hash)
    db_session_row = (await db_session.execute(stmt)).scalar_one()
    assert db_session_row.is_revoked is True


@pytest.mark.asyncio
async def test_inactive_user_cannot_authenticate(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that deactivated users are rejected upon login and protected routes."""
    reg_res = await async_client.post(
        "/api/auth/register",
        json={
            "email": "inactive@example.com",
            "display_name": "Inactive User",
            "password": "Pass123456",
        },
    )
    session_cookie = reg_res.cookies[settings.SESSION_COOKIE_NAME]

    # Deactivate user in database
    stmt = select(User).where(User.email == "inactive@example.com")
    user = (await db_session.execute(stmt)).scalar_one()
    user.is_active = False
    await db_session.commit()

    # Active session should now be rejected
    r_me = await async_client.get(
        "/api/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: session_cookie},
    )
    assert r_me.status_code == status.HTTP_401_UNAUTHORIZED

    # New login attempt should be rejected with 403
    r_login = await async_client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "Pass123456"},
    )
    assert r_login.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_expired_session_rejected(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that expired sessions return 401 Unauthorized."""
    reg_res = await async_client.post(
        "/api/auth/register",
        json={
            "email": "expired@example.com",
            "display_name": "Expired Tester",
            "password": "Pass123456",
        },
    )
    session_cookie = reg_res.cookies[settings.SESSION_COOKIE_NAME]

    # Manually backdate the session's expires_at in DB
    token_hash = hash_session_token(session_cookie)
    stmt = select(UserSession).where(UserSession.session_token_hash == token_hash)
    db_session_row = (await db_session.execute(stmt)).scalar_one()
    db_session_row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()

    # Accessing /api/auth/me should fail
    r_me = await async_client.get(
        "/api/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: session_cookie},
    )
    assert r_me.status_code == status.HTTP_401_UNAUTHORIZED
