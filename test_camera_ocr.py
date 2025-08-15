import os
import sys
import cv2
import numpy as np
from rapidocr import RapidOCR, EngineType, LangDet, LangRec, ModelType, OCRVersion
from PIL import Image, ImageDraw, ImageFont
import requests
import tempfile

def get_chinese_font(size=20):
    """获取中文字体"""
    try:
        # 尝试使用系统字体
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        
        # 如果没有找到字体，使用默认字体
        return ImageFont.load_default()
    except Exception as e:
        print(f"字体加载失败: {e}")
        return ImageFont.load_default()

def draw_chinese_text(image, boxes, texts, scores):
    """在图像上绘制中文文本"""
    # 将OpenCV图像转换为PIL图像
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image)
    
    # 获取中文字体
    font = get_chinese_font(20)
    
    for box, text, score in zip(boxes, texts, scores):
        # 获取文本框的左上角坐标
        x, y = int(box[0][0]), int(box[0][1])
        
        # 绘制文本和置信度
        text_with_score = f"{text} ({score:.2f})"
        
        # 绘制文本背景
        bbox = draw.textbbox((x, y-25), text_with_score, font=font)
        draw.rectangle(bbox, fill=(0, 255, 0, 128))
        
        # 绘制文本
        draw.text((x, y-25), text_with_score, font=font, fill=(0, 0, 0))
    
    # 将PIL图像转换回OpenCV格式
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

def main():
    # 设置控制台编码为UTF-8
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    
    # 初始化摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return

    # 设置摄像头分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # 创建窗口
    cv2.namedWindow('Camera')
    print("按空格键拍照，按ESC退出")

    # 初始化OCR
    det_path = os.path.join('lib', 'models', 'custom_det_model', 'det.onnx')
    rec_path = os.path.join('lib', 'models', 'custom_rec_model', 'rec.onnx')
    dict_path = os.path.join('lib', 'models', 'dict_custom_chinese_date.txt')

    params = {
        'Global.use_cls': False,
        'Det.engine_type': EngineType.ONNXRUNTIME,
        'Rec.engine_type': EngineType.ONNXRUNTIME,
        'Det.lang_type': LangDet.CH,
        'Rec.lang_type': LangRec.CH,
        'Det.model_type': ModelType.MOBILE,
        'Rec.model_type': ModelType.MOBILE,
        'Det.ocr_version': OCRVersion.PPOCRV5,
        'Rec.ocr_version': OCRVersion.PPOCRV5,
        'Det.model_path': det_path,
        'Rec.model_path': rec_path,
        'Rec.rec_keys_path': dict_path,
        'Det.box_thresh': 0.3,
        'Det.thresh': 0.1,
        'Det.unclip_ratio': 2.0,
        'Rec.rec_img_shape': [3, 48, 320],
    }

    try:
        ocr = RapidOCR(params=params)
        print("OCR初始化成功")
    except Exception as e:
        print(f"OCR初始化失败: {e}")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("无法获取图像")
            break

        # 显示实时画面
        cv2.imshow('Camera', frame)

        # 检测按键
        key = cv2.waitKey(1)
        if key == 27:  # ESC
            break
        elif key == 32:  # 空格
            print("\n正在识别...")
            try:
                # 执行OCR识别
                result = ocr(frame)
                if result is None or len(result.boxes) == 0:
                    print("未检测到文本")
                    continue

                print(f"\n检测到 {len(result.boxes)} 个文本框:")
                for i, (box, text, score) in enumerate(zip(result.boxes, result.txts, result.scores)):
                    # 确保文本正确编码
                    if isinstance(text, bytes):
                        text = text.decode('utf-8', errors='ignore')
                    elif not isinstance(text, str):
                        text = str(text)
                    
                    print(f"文本 {i+1}: {text} (置信度: {score:.3f})")
                    
                    # 在图像上绘制检测框
                    box = np.array(box, dtype=np.int32).reshape(-1, 1, 2)
                    cv2.polylines(frame, [box], True, (0, 255, 0), 2)

                # 使用PIL绘制中文文本
                frame_with_text = draw_chinese_text(frame, result.boxes, result.txts, result.scores)

                # 显示标注后的图像
                cv2.imshow('Result', frame_with_text)

            except Exception as e:
                print(f"识别失败: {e}")
                import traceback
                traceback.print_exc()

    # 释放资源
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()