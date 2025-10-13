# 使用更兼容的 Debian "slim" 版本作为基础镜像
FROM python:3.9-slim

# 声明并设置代理，以便在构建过程中使用
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY

# 安装 Chromium 浏览器及其依赖项，这对于 undetected-chromedriver 是必需的
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    curl \
    --no-install-recommends

# 设置环境变量，让 undetected_chromedriver 使用系统安装的驱动
# 这可以避免在Docker中自动下载驱动可能遇到的网络问题或权限问题
ENV DRIVER_EXECUTABLE_PATH=/usr/bin/chromedriver
# 自动检测并设置Chrome主版本号
RUN CHROME_MAJOR_VERSION=$(chromium --version | grep -oP 'Chromium \K\d+') && \
    echo "CHROME_VERSION=${CHROME_MAJOR_VERSION}" >> /etc/environment

# 设置时区为 GMT+8
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装两个文件中的依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个项目到工作目录
# 这会包括 forum_reply 目录, config 目录, 和所有 .py 文件
COPY . .

# 设置默认启动命令，指向正确的入口文件
CMD ["python", "forum_reply_main.py"]