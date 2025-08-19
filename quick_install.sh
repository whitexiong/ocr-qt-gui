#!/bin/bash

# OCR Camera 快速安装器 - 最简版本
# 使用方法: curl -fsSL https://raw.githubusercontent.com/whitexiong/ocr-qt-gui/master/quick_install.sh | bash

echo "🚀 OCR Camera 快速安装中..."

# 创建临时目录
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# 下载并解压
echo "📦 下载应用..."
curl -L -o ocr.tar.gz "https://github.com/whitexiong/ocr-qt-gui/releases/download/v1.0.0/OCRCamera.tar.gz"

echo "📂 解压应用..."
tar -xzf ocr.tar.gz

# 移动到用户目录
APP_DIR="$HOME/OCRCamera"
mv OCRCamera "$APP_DIR"

# 设置权限并启动
chmod +x "$APP_DIR/OCRCamera"
echo "✅ 安装完成！正在启动..."

cd "$APP_DIR"
./OCRCamera

# 清理临时文件
rm -rf "$TEMP_DIR"