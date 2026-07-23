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


def get_llm():
    try:
        import pymysql
        conn = pymysql.connect(
            host="127.0.0.1", port=3306, user="root",
            password="root", database="openwa", charset="utf8mb4"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT model_name, model_api_key FROM model LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return init_chat_model(row[0], api_key=row[1])
    except Exception as e:
        print(f"打印问题: {e}")

    return init_chat_model("deepseek-v4-flash")
