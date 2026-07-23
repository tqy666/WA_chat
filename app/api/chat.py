"""
    webhook模块，用户处理message.received和message.sent事件
"""
from fastapi import APIRouter,Request
from fastapi.responses import JSONResponse
from app.api.tasks import process_whatsapp_message
from dotenv import load_dotenv
import os


load_dotenv()
router = APIRouter()


@router.post("/webhook", )
async def handle_webhook(request: Request):

    body = await request.json()
    print("收到的数据:", body)

    # api_key = request.headers.get("x-api-key")
    # if not api_key or api_key !=  os.getenv("API_MASTER_KEY"):
    #     return JSONResponse(
    #         status_code=403,
    #         content={"status": "error", "message": "Invalid API Key"}
    #     )

    headers = dict(request.headers)
    print(f"打印头部消息：{headers}")

    process_whatsapp_message.delay(body)
    return {"status": "ok", "message": "queued"}
