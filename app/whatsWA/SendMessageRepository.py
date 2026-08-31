import httpx
import json
from dotenv import load_dotenv
import os

load_dotenv()


class SendMessageRepository:
    async def send_message(self, chatId, message, sessionId):
        api_key = os.getenv("API_MASTER_KEY")
        if not api_key:
            return {"statusCode": 500, "message": "Missing API Key"}

        url = f"{os.getenv("OPENWA_API_HOST")}/api/sessions/{sessionId}/messages/send-text"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": api_key
        }

        payload = {
            "chatId": chatId,
            "text": message
        }

        try:
            # 增加超时时间到 30 秒，防止因网络波动导致的假性 500
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                status = response.status_code
                print(f"🔹 HTTP Status: {status}")

                # 【关键】先不急着转 JSON，先看原始文本
                text_body = response.text
                print(f"🔹 Raw Response: {text_body[:200]}")

                # 如果是 2xx 状态码，说明发送成功
                if 200 <= status < 300:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        # 即使 JSON 解析失败，只要状态码是 200，也视为发送成功
                        print("⚠️ 警告: 响应不是标准 JSON，但状态码为 200，视为发送成功。")
                        return {"statusCode": 200, "message": "Sent (Non-JSON response)", "raw": text_body}

                # 如果不是 2xx，尝试解析错误信息
                try:
                    error_json = response.json()
                    return error_json
                except:
                    return {"statusCode": status, "message": "Request failed", "detail": text_body}

        except httpx.TimeoutException:
            print("⏰ 请求超时！但这可能意味着消息已在排队中。")
            # 这种情况下，消息很可能已经发了，只是没等到回执
            return {"statusCode": 202, "message": "Timeout but likely sent"}

        except Exception as e:
            print(f"❌ 发生未知异常: {str(e)}")
            return {"statusCode": 500, "message": str(e)}


# 保持单例模式
SendMessageRepository = SendMessageRepository()
