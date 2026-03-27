FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目依赖文件
COPY requirements.txt .

# 安装依赖选项使用清华源加速构建，并利用缓存层
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制整个项目代码
COPY . .

# 防止 Python 缓冲 stdout 和 stderr 导致 Docker 日志延迟
ENV PYTHONUNBUFFERED=1

# 默认启动命令
CMD ["python", "main.py"]
