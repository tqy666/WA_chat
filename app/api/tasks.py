# tasks.py
import asyncio
from app.api.celery_app import celery_app  # 确保这里导入的是你配置好的 celery app 实例
from app.whatsWA.ChatRepository import chatRepository  # 根据你的实际路径调整导入


@celery_app.task(
    name="process_whatsapp_message",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def process_whatsapp_message(self, body: dict):
    """
    异步处理 WhatsApp 消息
    """
    try:
        event = body.get("event")

        # 1. 简单的过滤逻辑保留
        if event != "message.received":
            return {"status": "ignored", "event": event}

        data = body.get("data", {})

        # 2. 构建查询参数 (保持原样)
        query = {
            "send_from": data.get("from"),
            "send_to": data.get("to"),
            "chatId": data.get("chatId"),
            "send_content": data.get("body"),
            "pushName": data.get("contact", {}).get("pushName"),
            "sessionId": body.get("sessionId"),
            "classification": None,
            "draft_response": None,
        }

        thread_id = data.get("chatId")

        # ==========================================
        # 3. 【关键修改】在这里运行异步函数
        # ==========================================
        print(f"[Celery] 开始处理消息: {query['send_content']}")

        # asyncio.run() 会创建一个新的事件循环并运行直到完成
        result = asyncio.run(
            chatRepository.chat_stream(thread_id, query)
        )

        print(f"[Celery] 处理完成: {result}")
        return {"status": "success", "result": str(result)}

    except Exception as e:
        print(f"[Celery] 处理失败: {e}")
        # 触发重试
        raise self.retry(exc=e)