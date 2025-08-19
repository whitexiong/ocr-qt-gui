# OCR Camera App

一个基于 PySide6 + RapidOCR 的桌面相机取图与文字识别应用

## 主要特性

- 🎥 **摄像头支持**：跨平台摄像头设备枚举（Windows DirectShow / Linux V4L2）
- 🖼️ **实时预览**：右侧实时画面 + 左侧分页结果（ID/文本/置信度）
- 📸 **智能拍照**：自动/手动拍照；检测触发；识别文本
- 🎯 **ROI 选择**：可视化区域选择；可配置预处理
- 💾 **数据存储**：SQLite 存储结果与配置
- ⚡ **多线程**：相机线程 + OCR 线程，保证界面流畅
- 📦 **一键打包**：提供 PyInstaller spec 脚本
- 🐳 **Docker 支持**：完整的容器化部署方案
- 🌍 **跨平台**：支持 Windows、Linux 系统
- 🎨 **中文支持**：完整的中文字体和界面支持

目录结构
```
qt_ocr_app/
  app/
    core/                # 核心模块（与 UI 无关）
      config.py          # 配置加载/保存和默认值，含路径自修复
      db.py              # SQLAlchemy 数据表与会话
      preprocess.py      # 图像预处理模块
    services/            # 运行时服务
      camera.py          # 相机线程（读取帧）
      ocr_worker.py      # OCR 线程（PaddleOCR-json 封装）
    ui/
      main_window.py     # 主窗口和 ROI 选择视图
    main.py              # 应用入口和控制器
  lib/                   # PaddleOCR-json 可执行文件与模型目录
    PaddleOCR-json.exe
    models/
  app_data/              # 应用本地数据（sqlite 等）
  qt_ocr_app.spec        # PyInstaller 打包配置
  run_app.ps1            # 运行脚本（Windows）
  requirements.txt
  README.md
```

## 快速开始

### 方法一：使用预编译的 Linux 可执行文件（推荐）

**适用于 Ubuntu/Debian 系统**

1. 下载项目并进入目录
2. 运行一键安装脚本：

```bash
bash install_ubuntu.sh
```

3. 启动应用程序：

```bash
# 命令行启动
./qt_ocr_app

# 或双击桌面快捷方式
```

详细安装说明请查看：[Ubuntu 安装指南](UBUNTU_INSTALLATION_GUIDE.md)

### 方法二：使用 Docker

#### 快速启动

1. 确保已安装 Docker 和 Docker Compose
2. 克隆项目到本地
3. 运行快速启动脚本：

```bash
# Windows
docker\quick_start.bat

# Linux/macOS
bash docker/quick_start.sh
```

#### Docker 容器详细操作

**构建 Docker 镜像**

```bash
# 进入 docker 目录
cd docker

# 构建镜像
docker-compose build

# 或者单独构建
docker build -t qt-ocr-app -f Dockerfile ..
```

**启动容器**

```bash
# 使用 docker-compose 启动（推荐）

# Windows 环境（支持摄像头，需要先配置 usbipd）
docker-compose up -d qt-app-windows

# Linux 环境
docker-compose up -d qt-app

# 或者直接运行容器（Windows）
docker run -d --name qt-ocr-app-win \
  -e DISPLAY=host.docker.internal:0.0 \
  -e QT_X11_NO_MITSHM=1 \
  -e QT_QPA_PLATFORM=xcb \
  -v "$(pwd)/../:/app" \
  -v /dev:/dev \
  --device=/dev/video0:/dev/video0 \
  --privileged \
  --network=host \
  qt-ocr-app
```

**注意**：Windows 环境下的摄像头支持需要：
1. 先按照上述步骤配置 usbipd-win
2. 确保摄像头设备已附加到 WSL2
3. 使用 `qt-app-windows` 服务启动容器

**进入容器**

```bash
# 进入运行中的容器
docker exec -it [ID] bash

# 或者启动一个新的交互式容器
docker run -it --rm \
  -v "$(pwd)/../:/app" \
  qt-ocr-app bash
```

**在容器内打包应用**

```bash
# 进入容器后，在 /app 目录下执行
cd /app

# 清理之前的构建
rm -rf build/ dist/

# 使用 PyInstaller 打包
python3 -m PyInstaller qt_ocr_app.spec --clean --noconfirm

# 打包完成后，可执行文件位于 dist/OCRCamera/ 目录
```

**启动打包后的应用**

```bash
# 在容器内启动（需要 X11 服务器）
cd /app
DISPLAY=host.docker.internal:0.0 ./dist/OCRCamera/OCRCamera

# 或者使用启动脚本
bash docker/start_app.sh
```

## 打包压缩

```bash
docker exec -it qt-ocr-app-win bash -c "cd /app && tar -czf OCRCamera.tar.gz -C dist OCRCamera" 
```

**Windows 摄像头配置（可选）**

如果需要在 Docker 容器中使用摄像头，需要先配置 usbipd：

```powershell
# 1. 安装 usbipd-win
winget install usbipd

# 2. 以管理员身份查看 USB 设备
usbipd list

# 3. 绑定摄像头设备（替换 <BUSID> 为实际的设备 ID）
usbipd bind --busid <BUSID>

# 4. 附加设备到 WSL2
usbipd attach --busid <BUSID> --wsl

# 5. 验证设备（在 WSL2 中）
wsl
ls /dev/video*
```

**X11 服务器设置（Windows）**

在 Windows 上需要安装 X11 服务器来显示 GUI：

```powershell
# 安装 VcXsrv（X11 服务器）
winget install VcXsrv

# 启动 X11 服务器
& "C:\Program Files\VcXsrv\vcxsrv.exe" :0 -ac -terminate -lesspointer -multiwindow -clipboard -wgl
```

**容器管理命令**

```bash
# 查看容器状态
docker ps -a

# 停止容器
docker stop qt-ocr-app

# 重启容器
docker restart qt-ocr-app

# 删除容器
docker rm qt-ocr-app

# 查看容器日志
docker logs qt-ocr-app

# 实时查看日志
docker logs -f qt-ocr-app
```

**容器内安装额外依赖**

```bash
# 进入容器
docker exec -it qt-ocr-app bash

# 更新包管理器
apt-get update

# 安装中文字体（如果需要）
apt-get install -y fonts-noto-cjk fonts-noto-cjk-extra fontconfig
fc-cache -fv

# 安装其他依赖
apt-get install -y <package-name>
```

### 方法三：本地开发环境

运行
- pip install -r requirements.txt
- powershell ./run_app.ps1

提示：首次启动会自动在 `app_data/` 下创建数据库；会检查 `lib/PaddleOCR-json.exe` 与 `lib/models`，不存在会回退到默认路径并写回配置。

打包（Windows）
pyinstaller qt_ocr_app.spec

说明：
- `qt_ocr_app.spec` 已包含 `lib/`、`app/ui`、`app/core`、`app/services`、`app_data` 目录。
- 需隐藏控制台可将 spec 中 `console=True` 改为 `False`。

## 故障排除

### Docker 环境摄像头问题

**问题**：在 Docker 容器中无法访问摄像头设备

**原因**：Windows Docker Desktop 需要通过 WSL2 和 usbipd 工具来访问 USB 摄像头设备 <mcreference link="https://github.com/microsoft/WSL/discussions/11230" index="1">1</mcreference> <mcreference link="https://github.com/docker/for-win/issues/13940" index="2">2</mcreference>

**解决方案**：

**方法一：使用 usbipd-win 工具（推荐）**

1. **安装 usbipd-win**：
   ```powershell
   # 使用 winget 安装
   winget install usbipd
   
   # 或从 GitHub 下载安装包
   # https://github.com/dorssel/usbipd-win/releases
   ```

2. **查看可用的 USB 设备**：
   ```powershell
   # 以管理员身份运行 PowerShell
   usbipd list
   ```

3. **绑定摄像头设备**：
   ```powershell
   # 绑定设备（需要管理员权限，只需执行一次）
   usbipd bind --busid <BUSID>
   
   # 例如：usbipd bind --busid 2-2
   ```

4. **附加设备到 WSL2**：
   ```powershell
   # 附加设备到 WSL2
   usbipd attach --busid <BUSID> --wsl
   
   # 例如：usbipd attach --busid 2-2 --wsl
   ```

5. **验证设备可用性**：
   ```bash
   # 在 WSL2 中检查设备
   wsl
   ls /dev/video*
   lsusb
   ```

6. **启动 Docker 容器**：
   ```bash
   # 使用 Windows 配置启动容器
   docker-compose up qt-app-windows
   ```

**方法二：本地环境（备选方案）**

如果 usbipd 配置复杂，推荐直接在 Windows 本地环境下使用：
1. 应用会显示"无可用摄像头 (Docker环境限制)"提示
2. 使用本地 Python 环境运行应用
3. Docker 环境主要用于开发和测试 OCR 功能

**注意事项**：
- usbipd 需要 Windows 10/11 和 WSL2 支持 <mcreference link="https://github.com/dorssel/usbipd-win/issues/353" index="4">4</mcreference>
- 某些摄像头可能需要在 WSL2 中安装特定驱动程序 <mcreference link="https://github.com/microsoft/WSL/discussions/11960" index="5">5</mcreference>
- 重启计算机后需要重新执行 `usbipd attach` 命令

### X11 显示问题

**问题**：GUI 界面无法显示

**解决方案**：
```bash
# 确保 X11 服务器正在运行
# Windows: 启动 VcXsrv
# Linux: 设置 DISPLAY 环境变量
export DISPLAY=:0
```

### 字体显示问题

**问题**：中文字符显示为方块

**解决方案**：
```bash
# 在容器内安装中文字体
docker exec -it qt-ocr-app bash
apt-get update
apt-get install -y fonts-noto-cjk fonts-noto-cjk-extra fontconfig
fc-cache -fv
```

## 开发说明

### 模型转换 (ONNX)

如需转换自定义 PaddleOCR 模型为 ONNX 格式：

```bash
# 创建新环境
conda create -n p2o-nightly python=3.10 -y
conda activate p2o-nightly

# 安装依赖
pip install --pre paddlepaddle -i https://www.paddlepaddle.org.cn/packages/nightly/cpu
pip install paddle2onnx==2.0.2rc3 rapidocr onnxruntime

# 转换模型
paddle2onnx --model_dir "path/to/custom_det_model" \
  --model_filename inference.json \
  --params_filename inference.pdiparams \
  --save_file "path/to/det.onnx" \
  --opset_version 13 \
  --enable_auto_update_opset True \
  --enable_onnx_checker True
```

### 项目结构说明

- `app/core/`：核心业务逻辑，与 UI 无关
- `app/services/`：后台服务（摄像头、OCR 等）
- `app/ui/`：用户界面组件
- `docker/`：Docker 相关配置文件
- `lib/models/`：OCR 模型文件
- `app_data/`：应用数据存储目录

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

- **v1.2.0**：添加 Docker 支持，修复跨平台摄像头兼容性
- **v1.1.0**：集成 RapidOCR，优化性能
- **v1.0.0**：初始版本，基于 PaddleOCR-json