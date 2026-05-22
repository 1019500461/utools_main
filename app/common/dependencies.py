from fastapi import Header, HTTPException
from jwt import DecodeError, ExpiredSignatureError

from app.core.security import decode_access_token
from app.modules.user.models import User


async def get_current_user(authorization: str = Header(default="")) -> User:
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = authorization[len(prefix) :]
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except DecodeError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = await User.filter(id=payload.get("user_id"), is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
