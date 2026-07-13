from typing import Annotated, TypedDict, Literal, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages, MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, CachePolicy, interrupt, Send
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy, TimeoutPolicy
from langgraph.errors import NodeError
from langchain_core.messages import (
    BaseMessage, SystemMessage, HumanMessage, ToolMessage
)
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from IPython.display import Image, display
from operator import add
from dotenv import load_dotenv
from pydantic.dataclasses import dataclass
from pydantic import BaseModel, Field

load_dotenv()
from typing import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage, SystemMessage


from typing import Annotated, List
import operator

# Evaluator-Optimizer: 生成广告语 → 评估 → 不达标则带着反馈重写
from typing import Literal


class AdState(TypedDict):
    product: str  # 产品名称
    slogan: str  # 当前广告语
    feedback: str  # 评估反馈
    grade: str  # 评分: "good" 或 "bad"
    iteration: int  # 当前迭代次数


# 模拟评估器（实际使用时用 llm.with_structured_output）
def evaluator_node(state: AdState):
    """评估广告语质量"""
    slogan = state["slogan"]
    iteration = state.get("iteration", 0)

    # 模拟评估逻辑：检查是否包含关键要素
    checks = []
    if len(slogan) < 10:
        checks.append("太短了，不够吸引人")
    if state["product"] not in slogan:
        checks.append(f"没有提到产品名'{state['product']}'")
    if "！" not in slogan and "!" not in slogan and "？" not in slogan:
        checks.append("缺少情感标点，不够有感染力")

    if not checks:
        return {"grade": "good", "feedback": ""}
    return {"grade": "bad", "feedback": "；".join(checks)}


def generate_slogan(state: AdState):
    """生成/改进广告语"""
    feedback = state.get("feedback", "")
    iteration = state.get("iteration", 0) + 1

    if feedback:
        print(f"  [第{iteration}轮] 根据反馈改进: {feedback}")
        # 模拟改进：根据反馈加长、加产品名、加感叹号
        new_slogan = f"🔥 {state['product']} 好啊！真滴棒！{state['product']} 好啊！顶呱呱！"
    else:
        new_slogan = f"{state['product']}真好"  # 故意生成一个不合格的
        print(f"  [第{iteration}轮] 初版生成: {new_slogan}")

    return {"slogan": new_slogan, "iteration": iteration}


def route_after_eval(state: AdState) -> Literal["generate", "__end__"]:
    """评估后路由：good→结束，bad→重新生成，超过3轮强制终止"""
    if state["grade"] == "good":
        print(f"  ✓ 评估通过！最终版本: {state['slogan']}")
        return END
    if state.get("iteration", 0) >= 3:
        print(f"  ⚠ 达到最大迭代次数，强制终止")
        return END
    return "generate"


eval_opt_graph = (
    StateGraph(AdState)
    .add_node("generate", generate_slogan)
    .add_node("evaluate", evaluator_node)
    .add_edge(START, "generate")
    .add_edge("generate", "evaluate")
    .add_conditional_edges("evaluate", route_after_eval, {
        "generate": "generate",  # 不达标→回generate重写
        END: END
    })
    .compile()
)

#display_graph(eval_opt_graph)

print("=== Evaluator-Optimizer: 广告语生成 ===\n")
r = eval_opt_graph.invoke({
    "product": "黑马程序员", "slogan": "", "feedback": "", "grade": "", "iteration": 0
})
print(f"\n最终广告语: {r['slogan']}")
print(f"总共迭代: {r['iteration']} 轮")