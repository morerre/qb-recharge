FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# 升级 pip
RUN pip install --upgrade pip

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制整个项目代码
COPY . .

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "app.py"]