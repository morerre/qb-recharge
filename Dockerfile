# 使用官方 Python 3.13 轻量镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (Playwright 需要)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && apt-get clean

# 预先升级 greenlet 到支持 Python 3.13 的版本
RUN pip install --upgrade pip && pip install 'greenlet>=3.1.0'

# 复制依赖文件并安装 Python 包 (避免自动重新解析 greenlet)
COPY requirements.txt .
RUN pip install --no-deps -r requirements.txt

# 安装 Playwright 浏览器 (Chromium)
RUN playwright install chromium

# 复制整个项目代码
COPY . .

# 暴露 Flask 默认端口
EXPOSE 5000

# 启动命令
CMD ["python", "app.py"]