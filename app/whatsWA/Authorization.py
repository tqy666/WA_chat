from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import pymysql
import bcrypt
# 导入刚才写的数据库查询函数
from app.config.MysqlConfig import get_user_from_db,get_user_permissions,create_active_user_db,update_user_password
from fastapi import  Depends, HTTPException, status

SECRET_KEY = "aB3xY9zQwE2rT5yU8iO1pA4sD6fG7hJ0kL2mN3vC5bX8zW1qE4rT6yU9iO0pA"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10080

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# OAuth2 密码流，指定获取 Token 的接口路径
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/token")


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserInDB(BaseModel):
    id: int
    username: str
    hashed_password: str
    disabled: bool



# ================= 辅助函数 =================

def get_user(username: str):
    """
    通过用户名获取用户对象
    现在它不再接收 db 参数，而是直接去查库
    """
    # 1. 调用数据库查询函数
    user_dict = get_user_from_db(username)

    # 2. 如果没查到，返回 None
    if not user_dict:
        return None

    # 3. 将查询到的字典转换为 Pydantic 模型 (UserInDB)
    # 注意：确保数据库字段名和模型字段名一致
    return UserInDB(**user_dict)


def verify_password(plain_password, hashed_password):
    """
    验证密码是否正确
    你需要引入 passlib 或 bcrypt 库来实现这个逻辑
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str):
    """
    认证用户
    """
    # 1. 获取用户
    user = get_user(username)

    # 2. 用户不存在或密码错误
    if not user or not verify_password(password, user.hashed_password):
        return False

    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt




async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"打印秘钥检测:{payload}")
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)

    except JWTError:
        raise credentials_exception

    return username



async def get_current_active_user(current_user = Depends(get_current_user)):

    print(f"打印鉴权用户的相关信息：{current_user}")
    if current_user:
        user = get_user_permissions(current_user)
        print(f"获取登录用户的信息：{user}")
        if user is None:
            return "401当前用户没有权限"
        return user

def create_active_user(username,password,role_id):

    insert_user = create_active_user_db(username,password,role_id)

    return insert_user

def change_password_user(old_password,new_password,user):
    search_user = get_user(user)
    if not user or not verify_password(old_password, search_user.hashed_password):
        return {"code":"400","message":"输入的原始密码有误"}
    update_user = update_user_password(search_user.id,new_password)
    return update_user

