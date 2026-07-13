from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat
from common.logger import setup_logging
# 初始化日志配置
setup_logging()

app = FastAPI(
    title="OpenWA",
    description="OpenWA钩子，WhatsApp用户询盘，后端直接回复响应",
    version="0.1.0"

)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议指定插件的 ID 或具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["会话"])


if __name__ == "__main__":
    import uvicorn

    # 启动命令：python -m app.main
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
