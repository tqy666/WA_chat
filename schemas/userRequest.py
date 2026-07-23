from typing import Optional, Dict, Any,List

from pydantic import BaseModel,Field

# ---  数据模型 ---
class UserRequest(BaseModel):
    # 消息内容
    username: str
    password: str
    role_id: int


class NewPasswordRequest(BaseModel):
    old_password:str
    new_password: str


class UserDisabledRequest(BaseModel):
    id:int
    disabled: int

class RoleRequest(BaseModel):
    role_name:str
    permissions_list:List[int]

class RoleChangeRequest(BaseModel):
    role_id:int
    user_id:int

class UserListRequest(BaseModel):
    current_page:int
    page_size:int

class RolePermissionsRequest(BaseModel):
    role_id:int
    permissions_id:List[int]

class CreatePermissionsRequest(BaseModel):
    permissions_name:str
    permissions_url:str

class editPermissionsRequest(BaseModel):
    permissions_id:int
    permissions_name: str
    permissions_url: str

class modelSettingRequest(BaseModel):
    model_name:str
    model_url: Optional[str] = Field(
        default=None,
        description="模型地址，可选",
    )
    model_api_key: str
    model_id:Optional[int] = Field(
        default=None,
        description="模型id，可选(更新模型时候必填)",
    )