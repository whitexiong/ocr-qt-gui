# run_onnx_ocr.py  —— ONNXRuntime + RapidOCR，路径写死，输出坐标/JSON，保存裁剪图与可视化
import os, sys, json, math
import cv2
import numpy as np
from rapidocr import RapidOCR, EngineType, LangDet, LangRec, ModelType, OCRVersion
from PIL import Image, ImageDraw, ImageFont

# ===== 固定路径 =====
IMAGE_PATH      = r"E:\workspace\jianxian-project\ocr\qt_ocr_app\test.jpg"
DET_ONNX        = r"E:\workspace\jianxian-project\ocr\qt_ocr_app\lib\models\custom_det_model\det.onnx"
REC_ONNX        = r"E:\workspace\jianxian-project\ocr\qt_ocr_app\lib\models\custom_rec_model\rec.onnx"
DICT_PATH       = r"E:\workspace\jianxian-project\ocr\qt_ocr_app\lib\models\dict_custom_chinese_date.txt"
OUT_DIR         = r"E:\workspace\jianxian-project\ocr\qt_ocr_app\out"
VIS_PATH        = os.path.join(OUT_DIR, "result_vis.jpg")
JSON_PATH       = os.path.join(OUT_DIR, "result.json")
CROPS_DIR       = os.path.join(OUT_DIR, "crops")
# ====================

# —— 推荐阈值（可按需微调）——
DET_BOX_THRESH  = 0.6     # 过滤框阈值（越高越严格）
DET_THRESH      = 0.3     # 二值化阈值
DET_UNCLIP      = 1.5     # 扩张比例（太小会切掉边，太大框会粘连）
REC_IMG_SHAPE   = [3, 48, 320]  # 识别输入尺寸，与你训练/导出的 rec.onnx 一致时效果最好

def ensure(p, name):
    if not os.path.exists(p):
        print(f"[错误] 找不到 {name}: {p}", file=sys.stderr); sys.exit(1)

def order_pts(pts):
    # pts: [(x,y)*4]  -> tl, tr, br, bl
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1); diff = np.diff(pts, axis=1).reshape(-1)
    tl = pts[np.argmin(s)]; br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]; bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

def crop_quad(img, quad):
    # 透视裁剪出正矩形
    quad = order_pts(quad)
    (tl, tr, br, bl) = quad
    wA = np.linalg.norm(br - bl); wB = np.linalg.norm(tr - tl)
    hA = np.linalg.norm(tr - br); hB = np.linalg.norm(tl - bl)
    W = int(max(wA, wB)); H = int(max(hA, hB))
    W = max(1, W); H = max(1, H)
    dst = np.array([[0,0],[W-1,0],[W-1,H-1],[0,H-1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img, M, (W, H))


def draw_vis(img, items, out_path):
    # 转成 Pillow 格式
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 字体路径（Windows 下用微软雅黑）
    font_path = r"C:\Windows\Fonts\msyh.ttc"
    font = ImageFont.truetype(font_path, 20)

    for box, text, _ in items:
        pts = [(int(x), int(y)) for x, y in box]
        # 绘制检测框（绿色）
        draw.line(pts + [pts[0]], fill=(0, 255, 0), width=2)
        # 绘制文字（红色）
        if text:
            draw.text((pts[0][0], max(0, pts[0][1] - 25)), text, font=font, fill=(255, 0, 0))

    # 转回 OpenCV 并保存
    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    cv2.imwrite(out_path, img_cv)
    print(f"[OK] 可视化已保存: {out_path}")

def to_items_struct(res):
    """统一成 [(box(4x2), text, score), ...]"""
    if hasattr(res, "boxes") and hasattr(res, "txts") and hasattr(res, "scores"):
        return list(zip(res.boxes, res.txts, res.scores)), getattr(res, "elapse_list", None)
    # 兼容旧返回 (list + times)
    if isinstance(res, tuple) and len(res)==2:
        return res[0], res[1]
    return [], None

def main():
    # 基础检查
    ensure(IMAGE_PATH, "测试图片")
    ensure(DET_ONNX,   "det.onnx")
    ensure(REC_ONNX,   "rec.onnx")
    ensure(DICT_PATH,  "字典文件（每行一个字符）")

    # 固定使用 ONNXRuntime，强制使用你的自定义字典，禁用方向分类器
    params = {
        "Global.use_cls": False,
        "Det.engine_type": EngineType.ONNXRUNTIME,
        "Rec.engine_type": EngineType.ONNXRUNTIME,
        "Det.lang_type":  LangDet.CH,
        "Rec.lang_type":  LangRec.CH,
        "Det.model_type": ModelType.MOBILE,
        "Rec.model_type": ModelType.MOBILE,
        "Det.ocr_version": OCRVersion.PPOCRV5,
        "Rec.ocr_version": OCRVersion.PPOCRV5,

        "Det.model_path": DET_ONNX,
        "Rec.model_path": REC_ONNX,

        # ★ 关键：自定义字典键名（避免走内置 dict_url）
        "Rec.rec_keys_path": DICT_PATH,

        # 常用后处理参数
        "Det.box_thresh": DET_BOX_THRESH,
        "Det.thresh": DET_THRESH,
        "Det.unclip_ratio": DET_UNCLIP,

        # 如果你的 rec.onnx 输入不是 3x48x320，改这里（例如 [3,32,320]）
        "Rec.rec_img_shape": REC_IMG_SHAPE,
    }

    # 读图
    img = cv2.imread(IMAGE_PATH, cv2.IMREAD_COLOR)
    if img is None:
        print(f"[错误] 读图失败: {IMAGE_PATH}", file=sys.stderr); sys.exit(1)

    # 推理
    ocr = RapidOCR(params=params)
    res = ocr(IMAGE_PATH, use_det=True, use_rec=True, use_cls=False)

    # 规整输出
    items, elapse = to_items_struct(res)

    # 打印+保存 JSON（坐标/文本/分数）
    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = []
    for i, (box, text, score) in enumerate(items):
        box = [[float(x), float(y)] for x, y in box]
        out_json.append({"id": i, "text": text, "score": float(score) if score is not None else None, "box": box})
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    print("[JSON 已保存]", JSON_PATH)

    # 保存裁剪贴片
    os.makedirs(CROPS_DIR, exist_ok=True)
    for i, (box, text, score) in enumerate(items):
        crop = crop_quad(img, box)
        cv2.imwrite(os.path.join(CROPS_DIR, f"{i:03d}_{text}.jpg"), crop)
    print(f"[Crops 已保存] {CROPS_DIR}  ({len(items)} 张)")

    # 可视化整图
    draw_vis(img.copy(), items, VIS_PATH)

    # 打印概要
    print("[文本结果]", [it["text"] for it in out_json])
    if isinstance(elapse, (list, tuple)) and all(isinstance(x, (int,float,type(None))) for x in elapse):
        d, c, r = [(x if isinstance(x, (int,float)) else float('nan')) for x in (elapse + [None,None,None])[:3]]
        print("[每阶段耗时(s)] det=%.4f  cls=%.4f  rec=%.4f" % (d, c, r))
    else:
        print("[每阶段耗时] N/A")

if __name__ == "__main__":
    main()
