OCR Camera App

- 基于 PySide6 + PaddleOCR-json 的桌面相机取图与日期识别应用
- 设备选择（枚举 OpenCV/DirectShow 设备）
- 右侧实时画面 + 左侧分页结果（ID/文本/置信度）
- 自动/手动拍照；检测触发；识别文本
- ROI 区域选择；可配置预处理
- SQLite 存储结果与配置
- 相机线程 + OCR 线程
- 提供 PyInstaller spec 脚本

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

运行
- pip install -r requirements.txt
- powershell ./run_app.ps1

提示：首次启动会自动在 `app_data/` 下创建数据库；会检查 `lib/PaddleOCR-json.exe` 与 `lib/models`，不存在会回退到默认路径并写回配置。

打包（Windows）
pyinstaller qt_ocr_app.spec

说明：
- `qt_ocr_app.spec` 已包含 `lib/`、`app/ui`、`app/core`、`app/services`、`app_data` 目录。
- 需隐藏控制台可将 spec 中 `console=True` 改为 `False`。

## 转换 onnx 新建立一个环境

```bash
conda create -n p2o-nightly python=3.10 -y
pip install --pre paddlepaddle -i https://www.paddlepaddle.org.cn/packages/nightly/cpu
pip install paddle2onnx==2.0.2rc3 rapidocr onnxruntime
paddle2onnx --model_dir "E:\workspace\jianxian-project\ocr\qt_ocr_app\lib\models\custom_det_model" --model_filename inference.json --params_filename inference.pdiparams --save_file "E:\workspace\jianxian-project\ocr\qt_ocr_app\lib\models\custom_det_model\det.onnx" --opset_version 13 --enable_auto_update_opset True --enable_onnx_checker True
```