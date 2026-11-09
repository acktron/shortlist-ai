from datetime import datetime,timedelta,timezone
import jwt
from fastapi import APIRouter,Depends,HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..deps import get_current_user, require_role
from ..models import User, Role
from ..schemas.auth import LoginRequest,TokenOut,UserOut
router=APIRouter(prefix="/auth",tags=["auth"]); pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
@router.post("/login",response_model=TokenOut)
def login(data:LoginRequest,db:Session=Depends(get_db)):
    user=db.query(User).filter(User.email==data.email.lower()).first()
    if not user or not pwd.verify(data.password,user.password_hash): raise HTTPException(401,"Invalid email or password")
    token=jwt.encode({"sub":str(user.id),"exp":datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expires_min)},settings.jwt_secret,algorithm="HS256")
    return {"access_token":token,"user":user}
@router.get("/me",response_model=UserOut)
def me(user:User=Depends(get_current_user)): return user
@router.get('/recruiter-check')
def recruiter_check(user:User=Depends(require_role(Role.recruiter, Role.delivery_head))): return {'ok':True}

