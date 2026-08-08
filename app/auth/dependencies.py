# app/auth/dependencies.py

from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.models.user import User
from app.schemas.user import UserResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    """Dependency to get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = User.verify_token(token)
    if token_data is None:
        raise credentials_exception

    try:
        # If the token data is a dictionary:
        if isinstance(token_data, dict):
            # If the payload contains a full set of user fields, use them directly.
            if "username" in token_data:
                return UserResponse(**token_data)
            # Otherwise, assume it is a minimal payload with only the 'sub' key.
            elif "sub" in token_data:
                return UserResponse(
                    id=token_data["sub"],
                    username="unknown",
                    email="unknown@example.com",
                    first_name="Unknown",
                    last_name="User",
                    is_active=True,
                    is_verified=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            else:
                raise credentials_exception

        # If the token data is directly a UUID (minimal payload):
        elif isinstance(token_data, UUID):
            return UserResponse(
                id=token_data,
                username="unknown",
                email="unknown@example.com",
                first_name="Unknown",
                last_name="User",
                is_active=True,
                is_verified=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        else:
            raise credentials_exception

    except Exception:
        raise credentials_exception
    
def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Dependency to get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user