from __future__ import annotations
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtGui import QImage, QPixmap, QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

class ChineseTextRenderer:
    """中文文本渲染器，用于在图像上绘制中文文本"""
    
    def __init__(self, font_size: int = 20):
        self.font_size = font_size
        self._font = None
        self._load_font()
    
    def _get_text_color(self):
        """根据当前主题获取文字颜色"""
        app = QApplication.instance()
        if app is None:
            return (0, 0, 0)  # 默认黑色
        
        # 获取当前调色板
        palette = app.palette()
        base_color = palette.color(QPalette.Base)
        
        # 判断是否为深色主题
        is_dark = (0.2126 * base_color.redF() + 0.7152 * base_color.greenF() + 0.0722 * base_color.blueF()) < 0.5
        
        # 深色主题使用白色文字，浅色主题使用黑色文字
        return (255, 255, 255) if is_dark else (0, 0, 0)
    
    def _load_font(self):
        """加载中文字体，支持Windows/Linux/Docker以及打包后的可执行环境"""
        try:
            search_paths = []
            # 优先使用项目内置字体（若存在）
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            project_fonts = [
                os.path.join(root, 'assets', 'fonts', 'NotoSansSC-Regular.otf'),
                os.path.join(root, 'assets', 'fonts', 'NotoSansSC-Regular.ttf'),
                os.path.join(root, 'assets', 'fonts', 'msyh.ttc'),
            ]
            search_paths.extend(project_fonts)

            # Windows 系统字体
            win_fonts = [
                "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
                "C:/Windows/Fonts/simhei.ttf",  # 黑体
                "C:/Windows/Fonts/simsun.ttc",  # 宋体
                "C:/Windows/Fonts/msyh.ttf",
            ]
            search_paths.extend(win_fonts)

            # Linux 常见中文字体（包含Docker场景）
            linux_fonts = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf",
                "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/arphic/ukai.ttf",
                "/usr/share/fonts/truetype/arphic/uming.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # 兜底
            ]
            search_paths.extend(linux_fonts)

            for font_path in search_paths:
                if os.path.exists(font_path):
                    try:
                        self._font = ImageFont.truetype(font_path, self.font_size)
                        return
                    except Exception:
                        continue

            # 如果没有找到字体，使用默认字体
            self._font = ImageFont.load_default()
        except Exception as e:
            print(f"字体加载失败: {e}")
            self._font = ImageFont.load_default()
    
    def draw_text_on_opencv_image(self, image: np.ndarray, boxes: list, texts: list, scores: list) -> np.ndarray:
        """在OpenCV图像上绘制中文文本
        
        Args:
            image: OpenCV图像 (BGR格式)
            boxes: 文本框坐标列表，每个框是四个点的坐标
            texts: 文本内容列表
            scores: 置信度列表
            
        Returns:
            绘制了文本的图像
        """
        if not boxes or not texts:
            return image.copy()
        
        # 将OpenCV图像转换为PIL图像
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)
        
        for box, text, score in zip(boxes, texts, scores):
            if not box or len(box) < 4:
                continue
                
            # 获取文本框的左上角坐标
            x, y = int(box[0][0]), int(box[0][1])
            
            # 确保文本正确编码
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='ignore')
            elif not isinstance(text, str):
                text = str(text)
            
            # 绘制文本和置信度
            text_with_score = f"{text} ({score:.2f})"
            
            # 计算文本边界框
            try:
                bbox = draw.textbbox((x, y-30), text_with_score, font=self._font)
                # 绘制半透明背景
                background = Image.new('RGBA', pil_image.size, (255, 255, 255, 0))
                bg_draw = ImageDraw.Draw(background)
                bg_draw.rectangle(bbox, fill=(0, 255, 0, 128))
                pil_image = Image.alpha_composite(pil_image.convert('RGBA'), background).convert('RGB')
                
                # 重新创建draw对象
                draw = ImageDraw.Draw(pil_image)
                
                # 绘制文本，使用动态颜色
                text_color = self._get_text_color()
                draw.text((x, y-30), text_with_score, font=self._font, fill=text_color)
            except Exception as e:
                print(f"绘制文本失败: {e}")
                # 降级处理：只绘制文本，不绘制背景，使用动态颜色
                text_color = self._get_text_color()
                draw.text((x, y-30), text_with_score, font=self._font, fill=text_color)
        
        # 将PIL图像转换回OpenCV格式
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    def draw_text_on_qimage(self, qimage: QImage, boxes: list, texts: list, scores: list) -> QImage:
        """在QImage上绘制中文文本
        
        Args:
            qimage: Qt图像
            boxes: 文本框坐标列表
            texts: 文本内容列表
            scores: 置信度列表
            
        Returns:
            绘制了文本的QImage
        """
        if not boxes or not texts:
            return qimage.copy()
        
        # 将QImage转换为numpy数组
        width = qimage.width()
        height = qimage.height()
        
        # 根据QImage格式转换
        if qimage.format() == QImage.Format_RGB888:
            ptr = qimage.constBits()
            arr = np.array(ptr).reshape(height, width, 3)
            # RGB to BGR for OpenCV
            opencv_image = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        elif qimage.format() == QImage.Format_BGR888:
            ptr = qimage.constBits()
            opencv_image = np.array(ptr).reshape(height, width, 3)
        else:
            # 转换为RGB888格式
            qimage = qimage.convertToFormat(QImage.Format_RGB888)
            ptr = qimage.constBits()
            arr = np.array(ptr).reshape(height, width, 3)
            opencv_image = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        
        # 绘制文本
        result_image = self.draw_text_on_opencv_image(opencv_image, boxes, texts, scores)
        
        # 转换回QImage
        rgb_image = cv2.cvtColor(result_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
    
    def set_font_size(self, size: int):
        """设置字体大小"""
        if size != self.font_size:
            self.font_size = size
            self._load_font()

# 全局实例
_renderer = None

def get_chinese_text_renderer(font_size: int = 20) -> ChineseTextRenderer:
    """获取中文文本渲染器实例"""
    global _renderer
    if _renderer is None or _renderer.font_size != font_size:
        _renderer = ChineseTextRenderer(font_size)
    return _renderer