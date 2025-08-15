import os
import sys
import cv2
import numpy as np
from rapidocr import RapidOCR, EngineType, LangDet, LangRec, ModelType, OCRVersion

def main():
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
                    print(f"文本 {i+1}: {text} (置信度: {score:.3f})")
                    # 在图像上绘制检测框
                    box = np.array(box, dtype=np.int32).reshape(-1, 1, 2)
                    cv2.polylines(frame, [box], True, (0, 255, 0), 2)
                    # 添加文本标注
                    x, y = box[0][0]
                    cv2.putText(frame, f"{text} ({score:.2f})", (x, y-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                # 显示标注后的图像
                cv2.imshow('Result', frame)

            except Exception as e:
                print(f"识别失败: {e}")
                import traceback
                traceback.print_exc()

    # 释放资源
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()