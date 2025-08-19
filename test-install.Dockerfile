# 测试安装脚本的Docker镜像
# 模拟客户的Ubuntu环境

FROM registry.cn-hangzhou.aliyuncs.com/library/ubuntu:20.04

# 设置非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# 安装基础工具
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# 创建测试用户
RUN useradd -m -s /bin/bash testuser && \
    echo 'testuser ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# 切换到测试用户
USER testuser
WORKDIR /home/testuser

# 设置环境变量
ENV HOME=/home/testuser

# 默认命令
CMD ["/bin/bash"]