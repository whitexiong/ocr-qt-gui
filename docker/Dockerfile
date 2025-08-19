# 使用Ubuntu 22.04作为基础镜像，包含更好的Qt支持
FROM ubuntu:22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:0
ENV QT_X11_NO_MITSHM=1
ENV QT_QPA_PLATFORM=xcb

# 安装Python和系统依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    binutils \
    v4l-utils \
    qt6-base-dev \
    qt6-qpa-plugins \
    libx11-xcb1 \
    libxkbcommon-x11-0 \
    libxcb-xinput0 \
    libfontconfig1 \
    libfreetype6 \
    libxext6 \
    libx11-6 \
    libxcb1 \
    libglib2.0-0 \
    libglx0 \
    libgl1 \
    libopengl0 \
    libegl1-mesa \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xkb1 \
    libdbus-1-3 \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# 配置字体缓存
RUN fc-cache -fv

# 创建python3的软链接
RUN ln -s /usr/bin/python3 /usr/bin/python

# 创建工作目录
WORKDIR /app

# 复制项目文件
COPY . /app/

# 配置pip镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 升级pip
RUN pip install --upgrade pip

# 复制并安装Python依赖
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# 设置Python路径环境变量
ENV PYTHONPATH=/app

# 设置默认命令
CMD ["python", "app/main.py"]