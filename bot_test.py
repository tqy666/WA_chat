import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
# 1. 导入 HTTPXRequest
from telegram.request import HTTPXRequest

from dotenv import load_dotenv
import os
load_dotenv()

# 设置环境变量（备用）
# os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'
# os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'

def run_langgraph(user_message: str) -> str:
    return f"AI 回复：{user_message}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"收到消息: {user_text}")
    ai_response = run_langgraph(user_text)
    await update.message.reply_text(ai_response)



if __name__ == '__main__':
        # 1. 创建请求对象，配置代理
        request = HTTPXRequest(proxy='http://127.0.0.1:7897')
        # #.request(request)  # 关键：这里直接传对象，不要加反斜杠 \
        # # 2. 构建应用
        app = (
            ApplicationBuilder()
            .token(os.getenv("YOUR_BOT_TOKEN"))
            .request(request)
            .build()
        )

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("Bot is running...")
        app.run_polling()

        #name:_6E82A9AED96BDDA0532DC5F87A7F295A.restcos.online
        #Point To:BE05C91DC778B424717035438E1F8E65.16BA41541D38E9A611273910AB5E11E7.1f75a87a8fd898f.comodoca.com
        #TTL:3600

