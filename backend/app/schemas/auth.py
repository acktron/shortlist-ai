from uuid import UUID
from pydantic import BaseModel, EmailStr
from ..models import Role
class LoginRequest(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel): id:UUID; email:EmailStr; full_name:str; role:Role; client_id:UUID|None
class TokenOut(BaseModel): access_token:str; token_type:str="bearer"; user:UserOut

