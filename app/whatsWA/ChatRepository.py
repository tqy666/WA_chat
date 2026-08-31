from typing import Literal, TypedDict

from langgraph.types import Command, RetryPolicy
from app.config.Setting import Settings, get_llm
from langgraph.graph import StateGraph, START, END
from pathlib import Path
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.whatsWA.RagRepository import RagServerTool
from app.whatsWA.FeishuRepository import FeishuReposirory
from app.whatsWA.SendMessageRepository import SendMessageRepository
# 意图识别的结构化输出
class WaClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex", "chit_chat"]
    urgency: Literal["low", "medium", "high", "critical"]


class WaAgentAgentState(TypedDict):
    # 原始消息
    send_from: str
    send_to: str
    chatId: str
    send_content: str
    pushName: str
    sessionId: str
    # 分类结果
    classification: WaClassification | None
    # 外部数据
    search_results: list[str] | None
    # 生成内容
    draft_response: str | None


class ChatRepository:
    def __init__(self):
        self.classifier_llm = get_llm()

    def read_message(self, state: WaAgentAgentState):
        """1. WhatsApp消息的起点"""
        print(f"收到WhatsApp客户：{state['send_from']}的消息")

    def classify_intent(self, state: WaAgentAgentState) -> Command[
        Literal["search_documentation", "send_message"]]:
        """2. LLM意图识别分类，决定走向知识库还是其他处理"""
        response = self.classifier_llm.invoke(f"""
                   分析用户的消息并分类,请严格按照 JSON 格式输出结果:
                   消息: {state['send_content']}
                   发件人: {state['send_from']}
                   提供 intent（question/bug/billing/feature/complex/human_agent）, urgency。
               """)
        import json
        import re
        # 从回复中提取 JSON
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        classification = json.loads(json_match.group()) if json_match else {"intent": "chit_chat", "urgency": "low"}
        print(f"意图识别：{classification}")
        if classification["intent"] in ["question", "feature"]:
            goto = "search_documentation"
        elif classification["intent"] == "chit_chat":
            return Command(
                update={
                    "classification": classification,
                    "draft_response": "您好！有什么我可以帮助您的吗？请随时提问。",
                },
                goto="send_message",
            )
        else:
            goto = "transfer_human_agent"
        return Command(
            update={"classification": classification},
            goto=goto
        )

    async def search_documentation(self, state: WaAgentAgentState) -> Command[Literal["send_message"]]:
        """3. 异步调用RAG知识库检索"""
        print("知识库搜索")
        rag_server = RagServerTool()
        rag_search = await rag_server.getKnowledge(state["send_content"])
        print(f"rag查询到的结果: {rag_search}")
        return Command(
            update={"draft_response": rag_search},
            goto="send_message"
        )

    async def transfer_human_agent(self, state: WaAgentAgentState) -> Command[Literal["send_message"]]:
        """转接人工客服，飞书通知"""
        print("通知飞书，转接人工客服")
        feishu_sever = FeishuReposirory()
        try:
            feishu_result = await feishu_sever.send_feishu_alert(state["send_from"], state["pushName"], state["send_content"])
            print(f"打印飞书传递回来的数据{feishu_result}")
            if feishu_result.get("code") == 200:
                return Command(
                    update={"draft_response": "已通知人工客服，请稍等.."},
                    goto="send_message"
                )
            else:
                return Command(
                    update={"draft_response": "抱歉，人工客服系统暂时繁忙，请稍后再试或直接拨打电话097366222。"},
                    goto="send_message"
                )
        except Exception as e:
            # 捕获非 API 逻辑错误（如网络断开）
            print(f"发生异常: {e}")
            return Command(
                update={"draft_response": "系统连接异常，请稍后再试。"},
                goto="send_message"
            )

    async def send_message(self, state: WaAgentAgentState):
        """4. 发送消息"""
        print(f"回复内容: {state['send_from']}-----{state['draft_response']}")
        message_result = await SendMessageRepository.send_message(state["chatId"], state["draft_response"], state["sessionId"])
        print(f"发送给WhatsApp消息:{message_result}")

    async def chat_stream(self, thread_id, query):
        wb_db = Path(__file__).resolve().parent.parent / "WhatsAppDB/wa_app.db"
        wb_db.parent.mkdir(parents=True, exist_ok=True)

        async with AsyncSqliteSaver.from_conn_string(str(wb_db)) as checkpointer:
            workflow = StateGraph(WaAgentAgentState)
            workflow.add_node("read_message", self.read_message)
            workflow.add_node("classify_intent", self.classify_intent)
            workflow.add_node(
                "transfer_human_agent",
                self.transfer_human_agent,
                retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0)
            )
            workflow.add_node(
                "search_documentation",
                self.search_documentation,
                retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0))
            workflow.add_node("send_message", self.send_message)

            workflow.add_edge(START, "read_message")
            workflow.add_edge("read_message", "classify_intent")
            workflow.add_edge("send_message", END)

            app = workflow.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            final_state = await app.ainvoke(query, config)
            return final_state


chatRepository = ChatRepository()


if __name__ == "__main__":
    thread_id = "5f875c42-16be-4415-84b3-6a6fa382ecd9"
    message = {
        "event": "message.received",
        "timestamp": "2026-07-18T13:54:53.362Z",
        "sessionId": "b628318e-d32c-493c-a6d1-cc0940f548f2",
        "idempotencyKey": "msg_b628318e-d32c-493c-a6d1-cc0940f548f2_unknown_3e9cceca-8508-4b73-9e30-5c4e0ca32326",
        "deliveryId": "dlv_857c0d44-d927-44b4-8e61-79c5b212b63e",
        "data": {
            "from": "210574529011868@lid",
            "to": "8617512019248@c.us",
            "chatId": "210574529011868@lid",
            "body": "Outdoor Power",
            "type": "text",
            "timestamp": 1784382892,
            "fromMe": False,
            "isGroup": False,
            "isStatusBroadcast": False,
            "isLidSender": True,
            "contact": {
                "pushName": "Juice-00",
                "name": "Juice-00"
            }
        }
    }
    query = {
        "send_from": message["data"]["from"],
        "send_to": message["data"]["to"],
        "chatId": message["data"]["chatId"],
        "send_content": message["data"]["body"],
        "pushName": message["data"]["contact"]["pushName"],
        "sessionId": message["sessionId"],
        "classification": None,
        "draft_response": None
    }
    import asyncio
    param = asyncio.run(chatRepository.chat_stream(thread_id, query))
    print(param)
