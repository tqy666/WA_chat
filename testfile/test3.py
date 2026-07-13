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


# 用于记录子任务信息的 结构化输出模型
class Section(BaseModel):
    name: str = Field(
        description="Name for this section of the report.",
    )
    description: str = Field(
        description="Brief overview of the main topics and concepts to be covered in this section.",
    )


class Sections(BaseModel):
    sections: List[Section] = Field(
        description="Sections of the report.",
    )

llm = init_chat_model("deepseek-chat")
# 将模型与structured output模型绑定，这个模型就用来拆分任务
planner = llm.with_structured_output(Sections)

# 编排者的 State ，记录完整信息
class State(TypedDict):
    topic: str  # 报告主题
    sections: list[Section]  # 报告的章节列表
    completed_sections: Annotated[
        list, operator.add
    ]  # 所有工作线程并行地把报告写入这个字段
    final_report: str  # 最终报告


# Worker的State，记录自己的任务进度
class WorkerState(TypedDict):
    section: Section
    completed_sections: Annotated[list, operator.add]

# 编排者节点
def orchestrator(state: State):
    """Orchestrator that generates a plan for the report"""

    # 通过SystemPrompt设定和结构化输出绑定，让LLM作为orchestrator
    report_sections = planner.invoke(
        [
            SystemMessage(content="Generate a plan for the report."),
            HumanMessage(content=f"Here is the report topic: {state['topic']}"),
        ]
    )
    print(report_sections)
    return {"sections": report_sections.sections}

# 工作节点，工作节点只能有1个，原因如下：
#  1.工作的代码逻辑是一样的，只是子任务不同
#  2.子任务数量不确定，无法提前给每个子任务写一个Node
# 我们会利用Send API来分发子任务给这个节点，让它产生“分身”效果，可以并行处理多个任务
def worker(state: WorkerState):
    """Worker writes a section of the report"""
    print(f"打印worker的数据：{state}")
    # 通过Prompt的设定，让llm根据子任务编写报告的部分章节
    section = llm.invoke(
        [
            SystemMessage(
                content="Write a report section following the provided name and description. Include no preamble for each section. Use markdown formatting."
            ),
            HumanMessage(
                content=f"Here is the section name: {state['section'].name} and description: {state['section'].description}"
            ),
        ]
    )

    # Write the updated section to completed sections
    return {"completed_sections": [section.content]}

# 合成器节点，用于合并最终结果
def synthesizer(state: State):
    """Synthesize full report from sections"""

    # 拿到Worker返回的结果
    completed_sections = state["completed_sections"]

    # 将完成的部分格式化为str，用作最后部分的上下文
    completed_report_sections = "\n\n---\n\n".join(completed_sections)

    return {"final_report": completed_report_sections}

from langgraph.types import Send

# Conditional edge Node，根据编排者安排的子任务创建llm_call工作者，每个工作者编写报告的一个部分
def assign_workers(state: State):
    """Assign a worker to each section in the plan"""
    for s in state["sections"]:
        print(f"打印section的内容：{s}")
    # 通过Send() API分发任务给Worker，让Worker并行写报告的不同章节
    return [Send("worker", {"section": s}) for s in state["sections"]]


# Build workflow
orchestrator_worker_builder = StateGraph(State)

# Add the nodes
orchestrator_worker_builder.add_node("orchestrator", orchestrator)
orchestrator_worker_builder.add_node("worker", worker)
orchestrator_worker_builder.add_node("synthesizer", synthesizer)

# Add edges to connect nodes
orchestrator_worker_builder.add_edge(START, "orchestrator")
orchestrator_worker_builder.add_conditional_edges(
    "orchestrator", assign_workers, ["worker"]
)
orchestrator_worker_builder.add_edge("worker", "synthesizer")
orchestrator_worker_builder.add_edge("synthesizer", END)

# Compile the workflow
orchestrator_worker_graph = orchestrator_worker_builder.compile()

# Show the workflow
# display_graph(orchestrator_worker_graph)

# Invoke
state = orchestrator_worker_graph.invoke({"topic": "创建一份关于LLM scaling laws的报告"})
print(state)
# from IPython.display import Markdown
# Markdown(state["final_report"])