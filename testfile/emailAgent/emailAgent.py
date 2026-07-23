from typing import TypedDict, Literal
from typing import Literal

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, RetryPolicy
from langchain.chat_models import init_chat_model
from app.config.Setting import Settings
from langgraph.types import interrupt

from pathlib import Path
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from app.config.Setting import Settings
import os
load_dotenv()

# 意图识别的结构化输出
class EmailClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str

# 邮件State
class EmailAgentState(TypedDict):
    # 原始输入
    email_content: str
    sender_email: str
    email_id: str
    # 分类结果
    classification: EmailClassification | None
    # 外部数据
    search_results: list[str] | None
    customer_history: dict | None
    # 生成内容
    draft_response: str | None



class EmailAgent:
    def __init__(self):
        pass
        #self.llm = Settings.Llm_qwen

    #llm = init_chat_model("deepseek-v4-flash")
    # llm = init_chat_model(
    #     model="qwen-plus",
    #     model_provider="openai",
    #     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    #     api_key=os.getenv("DASHSCOPE_API_KEY"),
    # )
    # 给LLM绑定结构化输出，做为路由决策
    classifier_llm = Settings.Llm_qwen.with_structured_output(EmailClassification)

    def read_email(self,state: EmailAgentState) -> dict:
        """节点1: 解析邮件——总是走到下一个固定节点"""
        # 真实业务可以连接邮件服务器，读取信息
        print(f"  [Read] 收到邮件: {state['email_id']}")
        return {}

    # 这里基于Command直接编写跳转规则，省去了conditional edge
    def classify_intent(self,state: EmailAgentState) -> Command[
        Literal["search_documentation", "bug_tracking", "draft_response"]]:
        """节点2: LLM分类 + 路由决策"""
        print(f"打印sate的值：{state}")
        # 先调用llm，做意图识别分类
        classification = self.classifier_llm.invoke(f"""
            分析这封客户邮件并分类,请严格按照 JSON 格式输出结果：
            邮件: {state['email_content']}
            发件人: {state['sender_email']}
            提供 intent（question/bug/billing/feature/complex）、urgency、topic、summary。
        """)
        print(f"意图识别：{classification}")
        # 根据分类结果决定数据 下个Node
        if classification['intent'] in ['question', 'feature']:
            goto = "search_documentation"
        elif classification['intent'] == 'bug':
            goto = "bug_tracking"
        else:
            # billing、complex → 跳过数据收集，直接生成草稿（draft 会判断是否需要人工审核）
            goto = "draft_response"

        print(f"  [Classify] intent={classification['intent']}, urgency={classification['urgency']}")
        print(f"  [Classify] -> 路由到: {goto}")
        return Command(
            update={"classification": classification},
            goto=goto
        )

    # 文档搜索/BUG工单处理完成后直接跳去draft_response，直接用Command跳转

    def search_documentation(self,state: EmailAgentState) -> Command[Literal['draft_response']]:
        """节点3: 搜索知识库（带重试策略）"""
        classification = state.get('classification', {})
        query = f"{classification.get('intent', '')} {classification.get('topic', '')}"
        print(f"  [Search] 查询: {query}")

        # 模拟知识库搜索，实际开发可以改为RAG
        search_results = [
            "密码重置: 登录 -> 设置 -> 安全 -> 修改密码",
            "密码至少12位，包含大小写和特殊字符",
            "两步验证开启方法: 安全设置 -> 两步验证"
        ]
        return Command(
            update={"search_results": search_results},
            goto="draft_response"
        )

    def bug_tracking(self,state: EmailAgentState) -> Command[Literal['draft_response']]:
        """节点4: 创建 Bug 工单"""
        ticket_id = f"BUG-{hash(state['email_id']) % 100000:05d}"
        print(f"  [BugTrack] 创建工单 {ticket_id}")

        return Command(
            update={
                "search_results": [f"Bug 工单 {ticket_id} 已创建"],
                "customer_history": {"ticket_id": ticket_id}
            },
            goto="draft_response"
        )

    print("节点 3-4 定义完成")

    def draft_response(self,state: EmailAgentState) -> Command[Literal["human_review", "send_reply"]]:
        """节点5: LLM生成回复草稿 + 判断是否需要人工审核"""
        classification = state.get('classification', {})

        # 格式化上下文（在节点内部格式化，不污染State）
        context_parts = []
        if state.get('search_results'):
            context_parts.append("文档:\n" + "\n".join(f"- {r}" for r in state['search_results']))
        if state.get('customer_history'):
            context_parts.append(f"工单: {state['customer_history']}")

        prompt = f"""起草一封回复邮件：
    客户: {state['sender_email']}
    原邮件: {state['email_content']}
    意图: {classification.get('intent')} | 紧急度: {classification.get('urgency')}
    {chr(10).join(context_parts)}

    要求：专业、友好、有针对性地解决用户问题。不超过100字。落款统一写“大海”。"""

        response = Settings.Llm_qwen.invoke(prompt)
        print(f"  [Draft] 回复已生成 ({len(response.content)} 字符)")
        print(f"[Draft] 回复:{response}")
        # 判断是否需要人工审核，对于紧急任务、复杂任务、账单相关，都走人工审核
        needs_review = (
                classification.get('urgency') in ['high', 'critical'] or
                classification.get('intent') in ['complex', 'billing']
        )
        goto = "human_review" if needs_review else "send_reply"
        print(f"  [Draft] -> 路由到: {goto}")

        return Command(update={"draft_response": response.content}, goto=goto)

    print("节点 5 定义完成")

    def human_review(self,state: EmailAgentState):
        """节点6: 人工审核"""
        classification = state.get('classification', {})

        human_decision = interrupt({
            "email_id": state.get('email_id', ''),
            "original_email": state.get('email_content', ''),
            "draft_response": state.get('draft_response', ''),
            "urgency": classification.get('urgency'),
            "intent": classification.get('intent'),
            "action": "请审阅并批准或编辑此回复,输入[approve 或 edit]"
        })
        print(f"打印人类中断事件：{human_decision}")
        # Now process the human's decision
        if human_decision.get("action") == 'edit':
            # edit，用户修改了邮件，需要更新State
            return {"draft_response": human_decision.get("edited_response")}
        else:
            # approve，没有修改邮件，直接发送
            return {}

    def send_reply(self,state: EmailAgentState) -> dict:
        """节点7: 发送邮件回复"""
        draft = state.get('draft_response', '')
        print(f"  [Send] 发送回复邮件给{state['sender_email']}成功...\n\n{draft}")
        return {}

    print("节点 6-7 定义完成")

    # 建立连接sqllite
    email_db = Path(__file__).resolve().parent.parent.parent / "emailChatDB/email_app.db"
    email_db.parent.mkdir(parents=True, exist_ok=True)
    sqlite_connection = sqlite3.connect(email_db, check_same_thread=False)
    #
    # # 2. 初始化 SqliteSaver
    checkpointer = SqliteSaver(sqlite_connection)

   #第二种连接MongoDB
    # from langgraph.checkpoint.mongodb import MongoDBSaver
    # from pymongo import MongoClient
    # client = MongoClient("mongodb://localhost:27017/")
    # checkpointer = MongoDBSaver(client)

    def getWorkFlow(self,query,config):


        workflow = StateGraph(EmailAgentState)

        # 添加所有节点
        workflow.add_node("read_email", self.read_email)
        workflow.add_node("classify_intent", self.classify_intent)
        # 带重试策略的节点
        workflow.add_node(
            "search_documentation",
            self.search_documentation,
            retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0)
        )
        workflow.add_node("bug_tracking", self.bug_tracking)
        workflow.add_node("draft_response", self.draft_response)
        workflow.add_node("human_review", self.human_review)
        workflow.add_node("send_reply", self.send_reply)

        # 定义最小边，大部分跳转都已通过Command实现，只用定义少量串行edge即可
        workflow.add_edge(START, "read_email")
        workflow.add_edge("read_email", "classify_intent")
        workflow.add_edge("human_review", "send_reply")
        workflow.add_edge("send_reply", END)

        # compile 时需要 checkpointer（interrupt 需要持久化）
        config1 = {"configurable": {"thread_id": "t1"}}
        app = workflow.compile(checkpointer=self.checkpointer)
        #newquery={"messages":[{"role":"user","content":"你还记得我吗"}]}
        for event in app.stream(query ,config,stream_mode=["values"]):
            #print(mode)
            print(f"打印输出：")
            print(event)

        # r1 = app.invoke(query, config)
        # return r1
    #display_graph(app)



if __name__=="__main__":
    EmailAgent = EmailAgent()

    # 测试三个不同场景

    # print("=== 场景1: 密码重置（查文档 → 自动回复）===\n")
    config1 = {"configurable": {"thread_id": "223"}}
    result = EmailAgent.getWorkFlow({
        "email_content": "Hi，我忘记登录密码了，如何重置？",
        "sender_email": "jack@example.com", "email_id": "email-001",
        "classification": None, "search_results": None,
        "customer_history": None, "draft_response": None
    },config1)

    print(result)

    # print(f"\n=== 场景2: Bug报告（建工单 → 回复）===\n")
    # config2 = {"configurable": {"thread_id": "t2"}}
    # query = {
    #     "email_content": "PDF导出功能每次都会崩溃，急需修复！",
    #     "sender_email": "jane@corp.com", "email_id": "email-002",
    #     "classification": None, "search_results": None,
    #     "customer_history": None, "draft_response": None, "messages": None
    # }
    # r2 = EmailAgent.getWorkFlow(query, config2)

    #print(f"  回复: {r2['draft_response']}...")

    # 人工确认，比如approve
    config3 = {"configurable": {"thread_id": "t2"}}
    # r4 = EmailAgent.getWorkFlow(
    #     Command(resume={
    #         "action": "edit",
    #         "edited_response": """
    #     尊敬的VIP客户jack，
    #
    #     非常抱歉给您带来不便！我们已紧急核查您的账户，确认存在重复扣款。我们将立即为您办理退款，预计1小时内原路返回。如有其他问题，请随时联系我们。再次感谢您的耐心！
    #
    #     大海
    #         """
    #     }),
    #     config3
    # )
    # result = EmailAgent.getWorkFlow([HumanMessage(content="Hi好")],config3)
    # print(result)

