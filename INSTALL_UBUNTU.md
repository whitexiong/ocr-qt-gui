# OCR Camera Ubuntu 安装指南

## 🚀 一键安装（推荐）

### 方法1: 在线安装
```bash
curl -fsSL https://your-server.com/install_ubuntu.sh | bash
```

### 方法2: 快速安装
```bash
curl -fsSL https://your-server.com/quick_install.sh | bash
```

## 📦 手动安装

### 1. 下载应用包
- 下载 `OCRCamera.tar.gz` 文件

### 2. 解压并运行
```bash
# 解压文件
tar -xzf OCRCamera.tar.gz

# 进入目录
cd OCRCamera

# 运行应用
./run_ocr_ubuntu.sh
```

## 🔧 系统要求

- Ubuntu 18.04 或更高版本
- 图形界面环境 (X11)
- 摄像头设备（可选）

## 📋 依赖说明

脚本会自动安装以下依赖：
- libgl1-mesa-glx
- libglib2.0-0  
- libxcb-xinerama0
- libfontconfig1
- libx11-xcb1

## 🎯 使用方法

### 启动应用
```bash
# 方法1: 使用启动脚本
./run_ocr_ubuntu.sh

# 方法2: 直接运行
./OCRCamera

# 方法3: 如果已安装到系统
ocr-camera
```

### 桌面快捷方式
安装后会自动创建桌面快捷方式，双击即可启动。

## 🐛 故障排除

### 问题1: 无法启动应用
```bash
# 检查依赖
ldd ./OCRCamera

# 安装缺失依赖
sudo apt update
sudo apt install -y libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0
```

### 问题2: 摄像头无法使用
```bash
# 检查摄像头权限
ls -l /dev/video*

# 添加用户到video组
sudo usermod -a -G video $USER
```

### 问题3: 显示问题
```bash
# 设置显示环境变量
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
```

## 📞 技术支持

如遇问题，请联系技术支持并提供以下信息：
- Ubuntu版本: `lsb_release -a`
- 错误信息截图
- 终端输出日志