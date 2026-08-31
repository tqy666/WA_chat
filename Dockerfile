# 1. 使用 Python 3.13 slim 版本 (匹配你的 pyproject.toml 要求)
FROM python:3.13-slim

# 2. 安装 uv (超快的包管理器)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 3. 设置工作目录
WORKDIR /app

# 4. 复制依赖文件
# 注意：这里只复制这两个文件，利用 Docker 缓存机制，只要依赖没变就不需要重新下载
COPY pyproject.toml uv.lock ./

# 5. 安装依赖
# --frozen: 严格按照 uv.lock 安装，保证环境一致性
# --no-dev: 生产环境不需要 ipython 等开发工具 (虽然你写在 dependencies 里了，加上这个更规范，如果报错可去掉)
RUN uv sync --frozen --no-cache

# 6. 复制剩余的项目代码
COPY . .

# 7. 暴露端口
EXPOSE 8000

# 8. 启动命令
# 使用 uv run 确保在虚拟环境中运行
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
