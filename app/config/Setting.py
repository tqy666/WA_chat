from langchain.chat_models import init_chat_model
from dataclasses import dataclass
from dotenv import load_dotenv
import os
load_dotenv()

@dataclass
class Settings:
    Llm = init_chat_model("deepseek-v4-flash")
    Llm_qwen = init_chat_model(
        model="qwen3.6-flash",
        model_provider="openai",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    )


Settings = Settings()