# app/api/userRequest.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import  OAuth2PasswordRequestForm
from datetime import timedelta
from app.whatsWA.Authorization import (Token,authenticate_user,ACCESS_TOKEN_EXPIRE_MINUTES,create_access_token,
                                       get_current_active_user,get_current_user,create_active_user,change_password_user)
from schemas.userRequest import (UserRequest, NewPasswordRequest, UserDisabledRequest, RoleRequest, RoleChangeRequest, UserListRequest,
                                 RolePermissionsRequest,CreatePermissionsRequest,editPermissionsRequest,modelSettingRequest)
from schemas.userResponse import PermissionResponse
from app.config.MysqlConfig import (change_disabled_user,change_del_user,create_role_permission,change_roleuser,
                                    get_user_list,gt_role_list,gt_role_list_with_perms,edit_role_permissions,del_role_permissions,get_all_permissions,
                                    buile_permission,permission_edite,permissions_disabled,setting_model,view_model)

router = APIRouter()



# ================= 接口路由 =================

@router.post("/token", response_model=Token,summary="登录获取Token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    登录接口：验证用户名密码并返回 JWT Token
    """
    # 直接调用 authenticate_user，传入表单里的用户名和密码
    print(f"打印form的数据：{form_data}")
    user = authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username,"user_id":user.id}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me",summary="获取当前登录用户的权限")
async def read_users_me(current_user= Depends(get_current_active_user)):
    """
        获取权限：获取当前登录的用户的权限
        """
    return current_user


@router.post("/users/create_user",summary="创建用户绑定角色")
async def create_user(request: UserRequest, user= Depends(get_current_user)):
    """
      创建用户：只有管理员能够创建用户,
      username:用户名,
      password：密码,
      role_id：角色id,
    """
    param = create_active_user(request.username,request.password,request.role_id)
    return param

@router.post("/users/change_password",summary="修改用户密码")
async def change_password(request: NewPasswordRequest, user=Depends(get_current_user)):
    """
      修改密码：所有用户都能修改密码,
      old_password:旧密码,
      new_password：新密码
    """
    print(f"获取用户名：{user}")
    edit_password = change_password_user(request.old_password,request.new_password,user)
    return edit_password

@router.post("/users/user_disabled",summary="禁用用户")
async def change_disabled(request:UserDisabledRequest,user=Depends(get_current_user)):
    """
      禁用用户：只有管理员才能禁用权限,
      id:int 用户id,
      disabled:int 禁用状态，0：表示正常，1表示禁止
    """
    disable_status = change_disabled_user(request.id,request.disabled)
    return disable_status

@router.delete("/users/user_del/{user_id}",summary="删除用户")
async def change_del(user_id:int,user=Depends(get_current_user)):
    """
          删除用户：只有管理员才有删除的权限,
          user_id:用户id
    """

    del_status = change_del_user(user_id)
    return del_status

@router.get("/users/get_user",summary="获取用户列表")
def get_user(current_page: int = Query(..., description="当前页数"), page_size: int = Query(..., description="页数"), user=Depends(get_current_user)):
    """
          获取用户列表列表：
          current_page：当前页数，
          page_size：页数
    """
    role_list =get_user_list(current_page,page_size)
    return role_list

@router.post("/users/user_role_edit",summary="修改用户和角色的绑定")
async def change_user_role(Request:RoleChangeRequest,user=Depends(get_current_user)):
    """
          修改用户绑定的角色：只有管理员才可以修改用户绑定的角色
          role_id:角色id,
          user_id:用户id
    """

    del_status = change_roleuser(Request.user_id,Request.role_id)
    return del_status

@router.post("/role/create_role",summary="创建角色和绑定权限")
def create_role(request:RoleRequest,user=Depends(get_current_user)):
    """
      创建角色和绑定权限：只有管理员才能创建角色绑定权限,
      role_name:角色名称,
      permissions_list：List[int] 多个权限id
    """

    role_result = create_role_permission(request.role_name,request.permissions_list)
    return role_result

@router.get("/role/get_role",summary="获取角色列表")
def get_role(user=Depends(get_current_user)):
    """
      角色列表：获取所有角色
    """

    role_result = gt_role_list_with_perms()
    return role_result

@router.post("/role/change_role_permissions",summary="修改角色绑定的权限")
def get_role(request:RolePermissionsRequest,user=Depends(get_current_user)):
    """
      修改角色和权限的绑定，
      role_id：int 角色id，
      permissions_id:List[int] 权限id
    """

    role_result = edit_role_permissions(request.role_id,request.permissions_id)
    return role_result

@router.delete("/role/{role_id}/del_role_permissions",summary="删除角色")
def del_role(role_id:int,user=Depends(get_current_user)):
    """
     删除角色，
     role_id：int 角色id，
     """
    del_result = del_role_permissions(role_id)
    return del_result

@router.get("/permissions/get_permissions",summary="获取所有权限列表")
def get_permission(current_page: int = Query(..., description="当前页数"), page_size: int = Query(..., description="页数"),user=Depends(get_current_user)):
    """
        获取所有的权限列表:
        --------is_on:0表示正常，1表示禁用-----
        {
         "code": 200,
         "message": "查询成功",
        "data": [
        {
            "id": 1,
            "permissions_name": "获取登录用户信息",
            "permissions_url": "/v1/users/me",
            "created_at": null,
            "is_on": 0
        }

    ]
}
    """

    all_permissions = get_all_permissions(current_page,page_size)
    return all_permissions


@router.post("/permissions/create_permissions",summary="创建权限")
def create_permission(request:CreatePermissionsRequest,user=Depends(get_current_user)):
    """
        创建权限，
        permissions_name：str 权限名称，
        permissions_url：str api接口地址
    """

    create_permission=buile_permission(request.permissions_name,request.permissions_url)
    return create_permission

@router.post("/permissions/edit_permissions",summary="修改权限")
def edit_permissions(request:editPermissionsRequest,user=Depends(get_current_user)):
    """
            编辑权限，
            permissions_id:int 权限id
            permissions_name：str 权限名称，
            permissions_url：str api接口地址
        """

    edi_permission = permission_edite(request.permissions_id,request.permissions_name, request.permissions_url)
    return edi_permission

@router.put("/permissions/{permissions_id}/disable_permissions/{is_on}",summary="禁用权限")
def disable_permissions(permissions_id,is_on,user=Depends(get_current_user)):
    """
        禁用权限，
        permissions_id:int 权限id,
        is_on：int (0:正常，1：禁用)
       """
    disabled_permissions = permissions_disabled(permissions_id,is_on)
    return disabled_permissions


@router.get("/model/model_list",summary="查看模型")
def model_list(user=Depends(get_current_user)):
    """"
        查看模型
    """
    list_model = view_model()
    return list_model

@router.post("/model/model_setting",summary="设置模型")
def model_setting(request:modelSettingRequest,user=Depends(get_current_user)):
    """"
        模型设置：
        model_name：str 模型名称
        model_url：str 模型地址默认为None,例如deepseek地址可以不填
        model_api_key:str 模型秘钥
        model_id：int 模型id
    """
    model_param = setting_model(request.model_name,request.model_url,request.model_api_key,request.model_id)
    return model_param
