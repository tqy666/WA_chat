import json
from idlelib import query
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.prompts import prompt
from langgraph.constants import START,END
from langgraph.graph import StateGraph

from app.config.Setting import Settings
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
from langchain_tavily import TavilySearch



#主图State
class TravelPlanSate(TypedDict):
    #用户输入
    start:str
    destination:str
    start_date:str
    end_date:str
    num_traveler:str
    budget:int


    #专家结果
    flight_professional:str
    hotel_professional :str
    activity_professional :str
    budget_breakdown:str

    #最终方案
    final_plan:str
    total_cost:float

#航班子图
class FlightSearchState(TypedDict):

    start: str
    destination: str
    start_date: str
    end_date: str|None
    num_traveler: int | None
    search_data:list
    recommend:list

#酒店子图
class HotelSearchState(TypedDict):

    start: str
    destination: str
    start_date: str
    end_date: str
    num_traveler: str
    search_data:list
    recommend:list

#活动子图
class ActivetySearchState(TypedDict):

    start: str
    destination: str
    start_date: str
    end_date: str
    num_traveler: str
    search_data:list
    recommend:list

###############工具和辅助函数############

async def search_flight_api(start,destination, date, traveler) -> list:
    # 查询航班

    # 3. 初始化 MCP 客户端
    client = MultiServerMCPClient({
        "travel_server": {
            "transport": "http",
            "url": "https://mcp.kiwi.com"
        },
        "time": {
            "transport": "stdio",
            "command": "uvx",
            "args": [
                "mcp-server-time",
                "--local-timezone=Asia/Shanghai"
            ]
        }
    })

    try:
        # 2. 获取工具列表
        tools = await client.get_tools()
        print(tools)
        # 3. 查找正确的工具名称 (注意是 search-flight)
        flight_tool = next((t for t in tools if t.name == "search-flight"), None)
        print(f"航班工具：{flight_tool}")
        if not flight_tool:
            return {"error": "未找到航班搜索工具"}

        # 4. 解析日期 (确保转换为 dd/mm/yyyy 格式)
        # 假设传入的 date 是 "2026-07-23" 这种标准格式
        from datetime import datetime
        try:
            dt_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = dt_obj.strftime("%d/%m/%Y")  # 转换为 23/07/2026
        except ValueError:
            # 如果传入的已经是 dd/mm/yyyy 或其他格式，视情况处理，这里做简单兼容
            formatted_date = date

            # 5. 解析人数 (简单提取数字)
        # 假设 traveler 字符串类似 "1 adult" 或 "2 adults"
        num_adults = 1
        if traveler:
            parts = str(traveler).split()
            if parts and parts[0].isdigit():
                num_adults = int(parts[0])
        print(f"打印num_adults：{num_adults}")
        # 6. 调用工具 (关键修正：使用正确的参数名)
        result = await flight_tool.ainvoke({
            "flyFrom": start,  # 修正：from -> flyFrom
            "flyTo": destination,  # 修正：to -> flyTo
            "departureDate": formatted_date,  # 修正：date -> departureDate
            "adults": num_adults,  # 修正：passengers -> adults
            "currency": "CNY",  # 可选：设置货币
            "locale": "zh"  # 可选：设置语言
        })
        #print(result)
        return result

    except Exception as e:
        return {"error": f"调用航班搜索失败: {str(e)}"}


def search_hotel_api(destination:str,checking:str,checkout:str,traveler:int)->list:
    #查询酒店
    query = f"""你要查看{destination}的酒店，入住时间：{checking}，退房时间：{checkout},一共是{traveler}人,要求评分最高，价钱最合适，交通最方便"""
    tavily_client = TavilySearch(max_results=3, topic="general")
    tavily_result = tavily_client.invoke({"query":query})
    print(tavily_result)
    return tavily_result


def search_activity_api(destination:str,start_date,num_traveler)->list:
    #搜索景点
    query = f"""你要查看{start_date}我们在{destination}的景点，一共是{num_traveler}人,要求评分最高，价钱最合适，交通最方便"""
    tavily_client = TavilySearch(max_results=3, topic="general")
    tavily_result = tavily_client.invoke({"query": query})
    print(tavily_result)
    return tavily_result

###############子图：航班专家#################

async def flight_search_node(state:FlightSearchState)->dict:
    """搜索航班:
     start: str
    destination: str
    start_date: str
    end_date: str | None
    num_traveler: int | None"""

    print("搜索航班")
    result = await search_flight_api(state["start"],state["destination"],state["start_date"],state["num_traveler"])

    return {"search_data":result}


def flight_recommend_node(state:FlightSearchState)->dict:
    """航班推荐专家"""
    print("AI分析航班")

    search_data=state["search_data"]

    """使用llm分析结果，取最终的一条结果"""
    prompt = f"""根据下面的航班内容,要求最经济，省时间，推荐最佳选项{json.dumps(search_data,ensure_ascii=False,indent=2)}"""
    search_response =Settings.Llm_qwen.invoke([HumanMessage(content=prompt)])
    #print(search_response.content)
    #recommend = [{"llm_recommendation":search_response.content}]
    return {"recommend":search_response.content}

#构建航班子图
flight_subgraph = StateGraph(FlightSearchState)
flight_subgraph.add_node("search",flight_search_node)
flight_subgraph.add_node("recommend",flight_recommend_node)
flight_subgraph.add_edge(START,"search")
flight_subgraph.add_edge("search","recommend")
flight_subgraph.add_edge("recommend",END)

flight_agent = flight_subgraph.compile()

# # 定义异步主函数
# async def main():
#     # 使用 await 和 ainvoke 进行异步调用
#     search_flight_data = await flight_agent.ainvoke({
#         "destination": "深圳",
#         "start_date": "2026年6月30日"
#     })
#     print(search_flight_data)
#
# if __name__=="__main__":
#     import asyncio
#    asyncio.run(main())



###############子图：酒店专家#################
def hotel_search_node(state:HotelSearchState)->dict:
    search_data = search_hotel_api(state["destination"],state['start_date'],state['end_date'],state["num_traveler"])
    return {"search_data":search_data}

def hotel_recommend_node(state:HotelSearchState)->dict:
    """"使用llm筛选最适合的酒店"""
    prompt =f"""挑选一个最适合的酒店，包含泳池，餐食，健身，推荐一个最佳的选择{json.dumps(state["search_data"],ensure_ascii=False,indent=2)}"""
    result = Settings.Llm_qwen.invoke([HumanMessage(content=prompt)])
    return {"recommend":result.content}

#构建酒店子图
hotel_subgraph = StateGraph(HotelSearchState)
hotel_subgraph.add_node("search_hotel",hotel_search_node)
hotel_subgraph.add_node("recommend_hotel",hotel_recommend_node)
hotel_subgraph.add_edge(START,"search_hotel")
hotel_subgraph.add_edge("search_hotel","recommend_hotel")
hotel_subgraph.add_edge("recommend_hotel",END)

hotel_agent = hotel_subgraph.compile()

#result = hotel_agent.invoke({"destination":"深圳"})
#print(result)


###############子图：活动专家#################
def activity_search_node(state:ActivetySearchState)->dict:
    result = search_activity_api(state["destination"],state["start_date"],state["num_traveler"])
    return {"search_data":result}

def activity_recommend_node(state:ActivetySearchState)->dict:
    prompt = f"""推荐一个景点，价格最适合，评分最高，最受大家最受欢迎的，下列选项选择{json.dumps(state["search_data"],ensure_ascii=False,indent=2)}"""
    search_active = Settings.Llm_qwen.invoke([HumanMessage(content=prompt)])
    #print(search_active.content)
    return {"recommend":search_active.content}

#构建酒店子图
activety_subgraph = StateGraph(ActivetySearchState)
activety_subgraph.add_node("activity_search",activity_search_node)
activety_subgraph.add_node("activity_recommend",activity_recommend_node)
activety_subgraph.add_edge(START,"activity_search")
activety_subgraph.add_edge("activity_search","activity_recommend")
activety_subgraph.add_edge("activity_recommend",END)

activety_agent = activety_subgraph.compile()

# result = activety_agent.invoke({"destination":"深圳"})
# print(result)


###################主图协调所有专家#######################

async def call_flight_agent(state:TravelPlanSate)->dict:
    search_flight_data = await flight_agent.ainvoke({"start":state["start"],"destination":state["destination"],"start_date":state["start_date"],"num_traveler":state["num_traveler"]})
    return  {"flight_professional":search_flight_data["recommend"]}

def call_hotel_agent(hotelsate:TravelPlanSate)->dict:
    search_hotel_data =hotel_agent.invoke({"start":hotelsate["start"],"destination":hotelsate["destination"],"start_date":hotelsate["start_date"],"end_date":hotelsate["end_date"],"num_traveler":hotelsate["num_traveler"]})
    return {"hotel_professional":search_hotel_data["recommend"]}

def call_activety_agent(activetysate:TravelPlanSate)->dict:
    search_hotel_data =activety_agent.invoke({"destination":activetysate["destination"],"start_date":activetysate["start_date"],"num_traveler":activetysate["num_traveler"]})
    return {"activity_professional":search_hotel_data["recommend"]}

def main_agent(mainstae:TravelPlanSate):
    final_plan = mainstae["flight_professional"]+mainstae["hotel_professional"]+mainstae["activity_professional"]
    return {"final_plan":final_plan}

#添加专家节点
main_graph = StateGraph(TravelPlanSate)
main_graph.add_node("call_flight_agent",call_flight_agent)
main_graph.add_node("call_hotel_agent",call_hotel_agent)
main_graph.add_node("call_activety_agent",call_activety_agent)
main_graph.add_node("main_agent",main_agent)
main_graph.add_edge(START,"call_flight_agent")
main_graph.add_edge(START,"call_hotel_agent")
main_graph.add_edge(START,"call_activety_agent")

main_graph.add_edge("call_flight_agent","main_agent")
main_graph.add_edge("call_hotel_agent","main_agent")
main_graph.add_edge("call_activety_agent","main_agent")
main_graph.add_edge("main_agent",END)
main_param = main_graph.compile()

# param = main_param.invoke({"destination":"shenzhen","start_date":"2026年7月30"})
# print(param['final_plan'])

# 定义异步主函数
async def main():
    # 使用 await 和 ainvoke 进行异步调用
    query = {
        "start": "深圳",
        "destination": "上海",
        "start_date": "2026-07-11",
        "end_date": "2026-07-15",
        "num_traveler": 5

    }

    search_flight_data = await main_param.ainvoke(query,)
    print(search_flight_data["final_plan"])

if __name__=="__main__":
    import asyncio
    asyncio.run(main())





