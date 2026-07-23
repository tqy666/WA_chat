import requests


def get_chat_history(session_id, api_key, target_chat_id):
    """
    获取指定客户的聊天记录
    :param session_id: 你的会话ID (例如 b628318e-d32c...)
    :param api_key: 你的 API Key
    :param target_chat_id: 目标客户的ID (例如 8617512019248@c.us)
    """

    # 1. 构造完整的 URL (把 :sessionId 替换成真实的 ID)
    base_url = "https://restcos.online"  # 注意：请确认你的 OpenWA 实例的实际域名，文档可能是 docs 域名
    url = f"{base_url}/api/sessions/{session_id}/messages"

    # 2. 设置请求头
    headers = {
        'X-API-Key': api_key,
        'Content-Type': 'application/json'
    }

    # 3. 设置查询参数 (这是关键！只查特定人的记录)
    params = {
        'chatId': target_chat_id,  # 必填：指定要查哪个客户
        'limit': 20,  # 选填：最近20条，避免数据太多
        'direction': 'all'
    }

    try:
        # 4. 发送 GET 请求
        response = requests.get(url, headers=headers, params=params)

        # 5. 检查状态码
        if response.status_code == 200:
            messages = response.json()
            print(f"成功获取到 {len(messages)} 条记录")
            print(f"打印输出的结果：{messages}")
            # 6. 打印最近的对话内容
            for msg in messages:

                sender = "我(AI)" if msg.get('fromMe') else "客户"
                body = msg.get('body', '')
                print(f"[{sender}]: {body}")

            return messages
        else:
            print(f"请求失败: {response.status_code}, 内容: {response.text}")
            return None

    except Exception as e:
        print(f"发生错误: {e}")
        return None


# --- 使用示例 ---
# 请替换为你自己的真实数据
MY_SESSION_ID = "b628318e-d32c-493c-a6d1-cc0940f548f2"
MY_API_KEY = "Kz8nR7D1qL9sX0pF2vB5gY6jC3mN4aT7hP9uS2dG5kZ8bQ1wE3rV6tJ0fM7cX9lD2sB5n"
CUSTOMER_ID = "210574529011868@lid"  # 从 Webhook 日志里拿到的那个 to 字段

get_chat_history(MY_SESSION_ID, MY_API_KEY, CUSTOMER_ID)