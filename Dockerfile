FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && apt-get clean

# 升级 pip
RUN pip install --upgrade pip

# 复制 requirements.txt 并安装所有依赖（自动处理依赖关系）
COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装 Playwright 浏览器
RUN playwright install chromium

# 复制整个项目代码
COPY . .

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "app.py"]