from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User, Role
bearer=HTTPBearer(auto_error=False)
def get_current_user(creds:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db))->User:
    if not creds: raise HTTPException(401,"Authentication required")
    try: uid=jwt.decode(creds.credentials,settings.jwt_secret,algorithms=["HS256"])["sub"]
    except (jwt.InvalidTokenError,KeyError): raise HTTPException(401,"Invalid or expired token")
    user=db.get(User,uid)
    if not user: raise HTTPException(401,detail={'code':'session_expired','message':'Your session expired, please sign in again.'})
    return user
def require_role(*roles:Role):
    def guard(user:User=Depends(get_current_user)):
        if user.role not in roles: raise HTTPException(403,"Insufficient permissions")
        return user
    return guard

