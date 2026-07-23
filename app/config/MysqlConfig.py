# app/config/MysqlConfig.py

import pymysql
from openai.types.beta.realtime import transcription_session_updated_event
from pymysql.cursors import DictCursor
from fastapi import   HTTPException
import bcrypt
from datetime import datetime

# ================= 1. 数据库配置 =================
DB_CONFIG = {
    "host": "localhost",  # 你的数据库地址
    "port": 3306,  # 端口
    "user": "root",  # 数据库用户名
    "password": "root",  # 数据库密码
    "database": "openwa",  # 你在 Navicat 中看到的数据库名
    "charset": "utf8mb4"
}


def get_user_from_db(username: str):
    """
    根据用户名从数据库中查询用户信息
    :param username: 用户名
    :return: 包含用户信息的字典 (如 {'id': 1, 'username': 'johndoe', ...})，如果未找到则返回 None
    """
    conn = None
    try:
        # 建立连接
        conn = pymysql.connect(**DB_CONFIG)
        # 使用 DictCursor，这样查询结果会自动变成字典格式 {'key': 'value'}
        with conn.cursor(DictCursor) as cursor:
            sql = "SELECT * FROM user WHERE username = %s"
            cursor.execute(sql, (username,))
            result = cursor.fetchone()  # 获取一行数据

            return result

    except Exception as e:
        print(f"数据库查询出错: {e}")
        return None
    finally:
        if conn:
            conn.close()

#获取用户的所有权限
def get_user_permissions(username: str):
    """
    获取指定用户的所有权限列表
    """
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        # ✅ 关键：使用 DictCursor，这样 row 就是字典，可以用 row['key'] 访问
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT 
                    u.id as uid,
                    u.username,       
                    r.role_name,      
                    p.permissions_name,
                    p.id as permissions_id,
                    p.permissions_url
                    
                FROM user u
                LEFT JOIN user_role ur ON u.id = ur.user_id
                LEFT JOIN role r ON ur.role_id = r.id
                LEFT JOIN role_permissions rp ON r.id = rp.role_id
                LEFT JOIN permissions p ON rp.permissions_id = p.id
                WHERE p.is_on=0 and u.username = %s
            """
            cursor.execute(sql, (username,))
            results = cursor.fetchall()  # 返回字典列表
            return results
            # ✅ 现在可以用字符串键访问了
            # 过滤掉 None 值（当用户没有权限时，p.permissions_name 会是 None）
            permissions = [row['permissions_name'] for row in results if row['permissions_name']]
            return permissions

    except Exception as e:
        print(f"查询权限出错: {e}")
        return []
    finally:
        if conn:
            conn.close()


def create_active_user_db(username,password,role_id):


    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        # ==========================================
        # 【新增】检查用户名是否重复
        # ==========================================
        check_sql = "SELECT id FROM user WHERE username = %s"
        cursor.execute(check_sql, (username,))

        # 如果 fetchone() 不为空，说明找到了同名用户
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"用户名 '{username}' 已存在，请更换一个"
            )

        # ==========================================
        # 2. 插入新用户
        # ==========================================
        # 注意：实际生产中密码必须加密（如 bcrypt），这里仅做演示
        password = password.encode('utf-8')  # 必须转为字节
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())  # 生成带盐的哈希值
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        insert_user_sql = "INSERT INTO user (username, hashed_password,created_at) VALUES (%s, %s, %s)"
        cursor.execute(insert_user_sql, (username, hashed, now_str))

        # 获取刚插入用户的自增 ID
        new_user_id = cursor.lastrowid

        # ==========================================
        # 3. 关联角色
        # ==========================================
        insert_role_sql = "INSERT INTO user_role (user_id, role_id) VALUES (%s, %s)"
        cursor.execute(insert_role_sql, (new_user_id, role_id))

        # 提交事务
        db.commit()

        return {"message": "创建成功", "user_id": new_user_id}

    except HTTPException as e:
        # 重新抛出我们自定义的错误（比如用户名重复）
        raise e
    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

#更新用户的密码
def update_user_password(uid,new_password):
    conn = None
    try:
        # 建立连接
        conn = pymysql.connect(**DB_CONFIG)
        # 使用 DictCursor，这样查询结果会自动变成字典格式 {'key': 'value'}
        password = new_password.encode('utf-8')  # 必须转为字节
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())  # 生成带盐的哈希值
        with conn.cursor(DictCursor) as cursor:
            sql = "UPDATE user SET hashed_password = %s WHERE id = %s"
            cursor.execute(sql, (hashed,uid))
            conn.commit()

            if cursor.rowcount == 0:
                return False  # 没找到用户
            return {"code":200,"message":"跟新成功"}

    except Exception as e:
        conn.rollback()
        print(f"数据库更新失败: {e}")
        return None
    finally:
        if conn:
            conn.close()

def change_disabled_user(id,disabled):
    conn = None
    try:
        # 建立连接
        conn = pymysql.connect(**DB_CONFIG)
        # 使用 DictCursor，这样查询结果会自动变成字典格式 {'key': 'value'}
        with conn.cursor(DictCursor) as cursor:
            sql = "UPDATE user SET disabled = %s WHERE id = %s"
            cursor.execute(sql, (disabled, id))
            conn.commit()

            if cursor.rowcount == 0:
                return False  # 没找到用户
            return {"code": 200, "message": "修改成功"}

    except Exception as e:
        conn.rollback()
        print(f"数据库更新失败: {e}")
        return None
    finally:
        if conn:
            conn.close()


def change_del_user(user_id):
    conn = None

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        # 第一步：删除角色关联
        sql_role = "DELETE FROM user_role WHERE user_id = %s"
        cursor.execute(sql_role, (user_id,))

        # 第二步：删除用户本身
        sql_user = "DELETE FROM user WHERE id = %s"
        cursor.execute(sql_user, (user_id,))

        # 提交事务
        conn.commit()
        print(f"用户 {user_id} 及其关联角色已彻底删除")
        return {"code":200,"message":"删除成功"}
    except Exception as e:
        # 如果任何一步出错，回滚所有操作
        conn.rollback()
        print(f"删除失败，已回滚: {e}")
    finally:
        cursor.close()


def change_roleuser(user_id,role_id):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        # ==========================================
        # 【新增】检查用户名是否重复
        # ==========================================
        sql = "UPDATE user_role SET role_id = %s WHERE user_id = %s"
        cursor.execute(sql, (role_id, user_id))

        # 提交事务
        db.commit()

        return {"code":200,"message": "修改用户角色成功"}

    except HTTPException as e:
        # 重新抛出我们自定义的错误（比如用户名重复）
        raise e
    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()


def create_role_permission(role_name, permissions_list):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        # ==========================================
        # 【检查】角色名是否重复
        # ==========================================
        check_sql = "SELECT id FROM role WHERE role_name = %s"
        cursor.execute(check_sql, (role_name,))

        # 调试打印
        print("执行的SQL:", cursor._executed)

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"用户名 '{role_name}' 已存在，请更换一个"
            )

        # ==========================================
        # 2. 插入新角色
        # ==========================================
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        insert_user_sql = "INSERT INTO role (role_name, created_at) VALUES (%s, %s)"
        cursor.execute(insert_user_sql, (role_name, now_str))

        # 获取刚插入角色的自增 ID
        new_role_id = cursor.lastrowid

        # ==========================================
        # 3. 关联权限 (批量插入)
        # ==========================================
        if permissions_list:
            # 构造数据列表: [(role_id, perm_id), (role_id, perm_id)...]
            data_to_insert = [(new_role_id, pid) for pid in permissions_list]

            insert_perm_sql = "INSERT INTO role_permissions (role_id, permissions_id) VALUES (%s, %s)"

            # 使用 executemany 批量插入
            cursor.executemany(insert_perm_sql, data_to_insert)

        # 提交事务
        db.commit()
        return {"message": "创建成功", "role_id": new_role_id}

    except HTTPException as e:
        # 如果是自定义的业务异常（如重名），回滚后抛出
        if db: db.rollback()
        raise e

    except Exception as e:
        # 其他所有异常，回滚并抛出 500 错误
        if db: db.rollback()
        # 打印详细错误以便调试
        print(f"数据库操作失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

    finally:
        # 确保资源释放
        if cursor: cursor.close()
        if db: db.close()


def get_user_list(current_page = 1,page_size = 10):


    db = None
    cursor = None

    offset = (current_page - 1) * page_size

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        check_sql = """
            SELECT u.id, u.username, u.disabled, u.created_at, ur.role_id, r.role_name
            FROM user u
            LEFT JOIN user_role ur ON u.id = ur.user_id
            LEFT JOIN role r ON ur.role_id = r.id
            LIMIT %s OFFSET %s
        """
        cursor.execute(check_sql, (page_size, offset))
        rows = cursor.fetchall()
        columns = ['id', 'username', 'disabled', 'created_at', 'role_id', 'role_name']
        result_list = []
        for row in rows:
            # zip(columns, row) 会把 ('id', 1), ('name', '获取...') 这样配对
            # dict(...) 将其转换为 {'id': 1, 'permissions_name': '获取...'}
            row_dict = dict(zip(columns, row))
            result_list.append(row_dict)

        # 如果还需要返回总条数（用于前端算总页数），需要再查一次 count
        count_sql = "SELECT COUNT(*) as total FROM user"
        cursor.execute(count_sql)
        total_count = cursor.fetchone()[0]
        print(total_count)
        return {
            "code": 200,
            "message": "查询成功",
            "data": result_list,
            "total": total_count,  # 总记录数
            "page": current_page,  # 当前页
            "page_size": page_size  # 每页大小
        }


    except HTTPException as e:
        # 重新抛出我们自定义的错误（比如用户名重复）
        raise e
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def gt_role_list():

    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        check_sql = "SELECT id, role_name, created_at FROM role "
        cursor.execute(check_sql, ())
        rows = cursor.fetchall()
        columns = ['id', 'role_name','created_at']
        result_list = []
        for row in rows:
            # zip(columns, row) 会把 ('id', 1), ('name', '获取...') 这样配对
            # dict(...) 将其转换为 {'id': 1, 'permissions_name': '获取...'}
            row_dict = dict(zip(columns, row))
            result_list.append(row_dict)



        return {
            "code": 200,
            "message": "查询成功",
            "data": result_list,
        }

    except HTTPException as e:
        raise e
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def gt_role_list_with_perms():
    db = None
    cursor = None

    try:
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        sql = """
            SELECT r.id, r.role_name, r.created_at, GROUP_CONCAT(rp.permissions_id) AS permissions_ids
            FROM role r
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            GROUP BY r.id
            ORDER BY r.id
        """
        cursor.execute(sql, ())
        rows = cursor.fetchall()
        columns = ['id', 'role_name', 'created_at', 'permissions_ids']
        result_list = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            if row_dict.get('permissions_ids'):
                row_dict['permissions_list'] = [int(x) for x in row_dict['permissions_ids'].split(',')]
            else:
                row_dict['permissions_list'] = []
            del row_dict['permissions_ids']
            result_list.append(row_dict)

        return {
            "code": 200,
            "message": "查询成功",
            "data": result_list,
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def edit_role_permissions(role_id,permissions_id):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        # 2. 清除旧数据
        delete_sql = "DELETE FROM role_permissions WHERE role_id = %s"
        cursor.execute(delete_sql, (role_id,))

        # 3. 批量插入新数据
        insert_data = [(role_id, pid) for pid in permissions_id]
        print(insert_data)
        if insert_data:
            insert_sql = "INSERT INTO role_permissions (role_id, permissions_id) VALUES (%s, %s)"
            # executemany 用于批量执行，效率更高
            cursor.executemany(insert_sql, insert_data)

        # 提交事务
        db.commit()

        return {"code": 200, "message": "修改角色和权限的绑定成功"}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def del_role_permissions(role_id):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        # 2. 清除权限和角色绑定
        delete_sql = "DELETE FROM role_permissions WHERE role_id = %s"
        cursor.execute(delete_sql, (role_id,))

        # 3. 清除user_id
        del_role_sql = "DELETE FROM role WHERE id = %s"
        cursor.execute(del_role_sql, role_id)

        # 提交事务
        db.commit()

        return {"code": 200, "message": "删除角色成功"}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def get_all_permissions(current_page=1,page_size=10):

    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        offset = (current_page - 1) * page_size

        sql = "select * FROM permissions LIMIT %s OFFSET %s"
        cursor.execute(sql, (page_size, offset))
        rows = cursor.fetchall()
        columns = ['id', 'permissions_name', 'permissions_url', 'created_at', 'is_on']
        result_list = []
        for row in rows:
            # zip(columns, row) 会把 ('id', 1), ('name', '获取...') 这样配对
            # dict(...) 将其转换为 {'id': 1, 'permissions_name': '获取...'}
            row_dict = dict(zip(columns, row))
            # 将 datetime 对象转为 ISO 字符串，避免 Pydantic 校验失败
            if isinstance(row_dict.get('created_at'), datetime):
                row_dict['created_at'] = row_dict['created_at'].isoformat()
            result_list.append(row_dict)

        count_sql = "SELECT COUNT(*) as total FROM permissions"
        cursor.execute(count_sql)
        total_count = cursor.fetchone()[0]
        print(total_count)

        return {
            "code": 200,
            "message": "查询成功",
            "data": result_list,
            "total": total_count,  # 总记录数
            "page": current_page,  # 当前页
            "page_size": page_size  # 每页大小
        }


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def buile_permission(permissions_name,permissions_url):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        # 2. 清除旧数据
        delete_sql = "select * FROM permissions WHERE permissions_name = %s or permissions_url = %s"
        cursor.execute(delete_sql, (permissions_name,permissions_url))


        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"用户名 '{permissions_name}和permissions_url' 已存在，请更换一个"
            )

        # 3. 批量插入新数据
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        insert_sql = "INSERT INTO permissions (permissions_name, permissions_url,created_at) VALUES (%s, %s, %s)"
        cursor.execute(insert_sql, (permissions_name, permissions_url,now_str))

        # 提交事务
        db.commit()

        return {"code": 200, "message": "创建权限成功"}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def permission_edite(permissions_id,permissions_name,permissions_url):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        sql = "UPDATE permissions SET permissions_name = %s,permissions_url=%s WHERE id = %s"
        cursor.execute(sql, (permissions_name, permissions_url,permissions_id))

        # 提交事务
        db.commit()

        return {"code": 200, "message": "权限修改成功"}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()


def permissions_disabled(permissions_id,is_on):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        sql = "UPDATE permissions SET is_on = %s WHERE id = %s"
        cursor.execute(sql, (is_on, permissions_id))

        # 提交事务
        db.commit()

        return {"code": 200, "message": "权限修改成功"}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def setting_model(model_name,model_url,model_api_key,model_id):

    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        if model_id is  None:
            sql = "INSERT INTO model (model_name, model_url,model_api_key) VALUES (%s, %s, %s)"
            cursor.execute(sql, (model_name, model_url, model_api_key))
        else:

            sql = "UPDATE model SET model_name = %s,model_url = %s,model_api_key = %s WHERE id = %s"
            cursor.execute(sql, (model_name, model_url,model_api_key,model_id))

        # 提交事务
        db.commit()

        return {"code": 200, "message": "模型配置成功"}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()


def view_model():
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        model_sql = "select * FROM model "
        cursor.execute(model_sql, ())
        rows = cursor.fetchall()
        columns = ['model_id', 'model_name', 'model_url', 'model_api_key']
        result_list = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            result_list.append(row_dict)


        return {"code": 200, "message": "模型查询成功","data":result_list}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def check_content_repeat(hash_md5):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        model_sql = "select md5_hash FROM file_chunk where md5_hash = %s"
        cursor.execute(model_sql, (hash_md5))
        rows =  cursor.fetchone()

        return rows

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()

def insert_chunk_data(hash_mad5,collection_name,filename,file_size,len_chunks,file_paths,ids,date):

    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()


        sql = ("INSERT INTO file_chunk ( md5_hash, collections, filename, file_size,chunk, file_path, ids, creat_time) "
               "VALUES (%s, %s, %s,%s, %s, %s,%s, %s)")
        cursor.execute(sql, (hash_mad5, collection_name, filename,file_size,len_chunks,file_paths,ids,date))

        # 提交事务
        db.commit()

        return cursor.lastrowid

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()


def get_file_list(id=None):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        if id:
            sql  = "select file_path,ids from file_chunk where id = %s"
            cursor.execute(sql, (id))
            rows = cursor.fetchone()
            return rows
        else:

            model_sql = "select id,filename,file_size,chunk,creat_time from file_chunk  "
            cursor.execute(model_sql, ())
            rows = cursor.fetchall()
            columns = ['id', 'filename','file_size','chunk','creat_time']
            result_list = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                result_list.append(row_dict)

            return {"code": 200, "message": "查询成功", "data": result_list}

    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()


def del_file_data(id):
    db = None
    cursor = None

    try:
        # 1. 建立连接
        db = pymysql.connect(**DB_CONFIG)
        cursor = db.cursor()

        sql = "DELETE FROM file_chunk WHERE id = %s"
        result = cursor.execute(sql, (id))
        # 提交事务
        db.commit()
        return result
    except Exception as e:
        # 其他错误回滚
        if db: db.rollback()
        raise HTTPException(status_code=500, detail=f" {str(e)}")
    finally:
        if cursor: cursor.close()
        if db: db.close()
