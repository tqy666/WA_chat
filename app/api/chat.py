"""
    webhook模块，用户处理message.received和message.sent事件
"""
from fastapi import APIRouter,Request
from app.whatsWA.ChatRepository import chatRepository
router = APIRouter()


@router.post("/webhook", )
async def handle_webhook(request: Request):

    headers = dict(request.headers)
    print(f"打印头部消息：{headers}")
    #print(f"打印Token：{headers["authorization"]}")
    body = await request.json()
    # print("收到的数据:", body)
    # return {"status": "ok", "message": "received"}

    #param =  await chatRepository.chat_stream(body)
    print(f"获取到的值：{body}")
    thread_id = "5f875c42-16be-4415-84b3-6a6fa382ecd9"
    query = {
        "send_from": body["data"]["from"],
        "send_to": body["data"]["to"],
        "chatId": body["data"]["chatId"],
        "send_content": body["data"]["body"],
        "pushName": body["data"]["contact"]["pushName"],
        "sessionId": body["sessionId"],
        "classification": None,
        "draft_response": None
    }
    param = await chatRepository.chat_stream(thread_id,query)
    print(param)