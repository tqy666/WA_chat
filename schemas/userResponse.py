from pydantic import BaseModel
from typing import List, Optional

# 1. 定义单个权限的模型
class PermissionItem(BaseModel):
    id: int
    permissions_name: str
    permissions_url: str
    created_at: Optional[str] = None
    is_on: int


class PermissionResponse(BaseModel):
    code: int
    message: str
    data: List[PermissionItem]

