"""
    webhook模块，用户处理message.received和message.sent事件
"""
from fastapi import APIRouter,Request

router = APIRouter()


@router.post("/wa/webhook", tags=["获取WhatsApp钩子消息"])
async def handle_webhook(request: Request):
    body = await request.json()  # ✅ 读取并解析 JSON 请求体
    print("收到的数据:", body)
    return {"status": "ok", "message": "received"}


    # event = request.json.get("event")
    # if event == "message.received":
    #     return handle_incoming_message(request.json)
    # elif event == "message.sent":
    #     return handle_outgoing_confirmation(request.json)
    # elif event == "message.failed":
    #     return handle_send_failure(request.json)
    # else:
    #     return {"status": "ignored", "event": event}







