#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
改进版的OCR系统，使用PaddleOCR-json架构实现多层级识别策略
支持：自定义模型 -> PaddleOCR API -> 远程API的三级fallback机制
"""

import os
import re
import json
import time
import cv2
import numpy as np
import requests
from typing import List, Dict, Any, Optional, Tuple
import logging

# 设置PaddleOCR日志级别，去除警告和调试信息
import warnings
warnings.filterwarnings('ignore')

# 设置环境变量来控制Paddle的日志级别
os.environ['FLAGS_log_level'] = '3'  # Paddle框架日志级别
os.environ['GLOG_v'] = '0'  # 详细日志级别
os.environ['GLOG_minloglevel'] = '3'  # 最小日志级别
os.environ['GLOG_logtostderr'] = '0'  # 禁止输出到stderr

# 配置Python日志系统
logging.getLogger('ppocr').setLevel(logging.ERROR)
logging.getLogger('paddle').setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

# 禁用Paddle调试信息
import paddle
paddle.disable_signal_handler()  # 禁用Paddle的信号处理器

# 添加PaddleOCR路径
import sys
sys.path.insert(0, '.')

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiLevelOCR:
    """多层级OCR识别系统"""
    
    def __init__(self, 
                 custom_config_path: str = None,
                 ppocr_config_path: str = None,
                 api_config: Dict[str, Any] = None,
                 confidence_threshold: float = 0.90):
        """
        初始化多层级OCR系统
        
        Args:
            custom_config_path: 自定义模型配置文件路径
            ppocr_config_path: PaddleOCR默认配置文件路径 
            api_config: API配置信息
            confidence_threshold: 置信度阈值，低于此值将使用下一级识别
        """
        self.confidence_threshold = confidence_threshold
        self.api_config = api_config or {}
        
        # 初始化参数
        self.args = self._init_args()
        
        # 初始化检测器和识别器
        try:
            from tools.infer.predict_det import TextDetector
            from tools.infer.predict_rec import TextRecognizer
            
            # 初始化自定义模型
            self.custom_detector = TextDetector(self.args)
            self.custom_recognizer = TextRecognizer(self.args)
            logger.info("✅ 自定义模型初始化成功")
            
            # 初始化默认模型
            default_args = self._init_default_args()
            self.default_detector = TextDetector(default_args)
            self.default_recognizer = TextRecognizer(default_args)
            logger.info("✅ 默认模型初始化成功")
            
        except Exception as e:
            logger.error(f"模型初始化失败: {e}")
            raise
    
    def _init_args(self):
        """初始化自定义模型参数"""
        from tools.infer.utility import init_args, parse_args
        args = parse_args()
        
        # 检测模型配置
        args.det_algorithm = "DB"
        args.det_model_dir = "./inference/det_model"
        args.det_limit_side_len = 960
        args.det_db_thresh = 0.3
        args.det_db_box_thresh = 0.6
        args.det_db_unclip_ratio = 1.5
        args.use_dilation = False
        
        # 识别模型配置
        args.rec_algorithm = "SVTR_LCNet"
        args.rec_model_dir = "./inference/rec_model"
        args.rec_image_shape = "3, 48, 320"
        args.rec_batch_num = 6
        args.max_text_length = 25
        args.rec_char_dict_path = "./ppocr/utils/dict/custom_chinese_date_dict.txt"
        args.use_space_char = True
        args.drop_score = 0.5
        
        # GPU配置
        args.use_gpu = True
        args.gpu_mem = 500
        args.ir_optim = True
        args.use_tensorrt = False
        args.use_fp16 = False
        
        return args
    
    def _init_default_args(self):
        """初始化默认模型参数"""
        from tools.infer.utility import init_args, parse_args
        args = parse_args()
        
        # 检测模型配置
        args.det_algorithm = "DB"
        args.det_model_dir = "./lib/models/ch_PP-OCRv3_det_infer"
        args.det_limit_side_len = 960
        args.det_db_thresh = 0.3
        args.det_db_box_thresh = 0.6
        args.det_db_unclip_ratio = 1.5
        args.use_dilation = False
        
        # 识别模型配置
        args.rec_algorithm = "SVTR_LCNet"
        args.rec_model_dir = "./lib/models/ch_PP-OCRv3_rec_infer"
        args.rec_image_shape = "3, 48, 320"
        args.rec_batch_num = 6
        args.max_text_length = 25
        args.rec_char_dict_path = "./lib/models/dict_chinese.txt"
        args.use_space_char = True
        args.drop_score = 0.5
        
        # GPU配置
        args.use_gpu = True
        args.gpu_mem = 500
        args.ir_optim = True
        args.use_tensorrt = False
        args.use_fp16 = False
        
        return args
    
    def _read_config(self, config_path: str) -> Dict[str, str]:
        """读取配置文件"""
        config = {}
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        config[parts[0]] = parts[1]
        return config
    
    def preprocess_image(self, img):
        """图像预处理"""
        if isinstance(img, str):
            # 如果输入是图片路径
            if not os.path.exists(img):
                raise FileNotFoundError(f'{img} 不存在')
            img = cv2.imread(img)
        if img is None:
            raise ValueError('图片加载失败')
        return img

    def get_rotate_crop_image(self, img, points, expand_ratio=0.1, upscale_factor=2.0):
        """获取旋转裁剪的图像，增加边距和分辨率"""
        # 计算最小外接矩形
        points = np.array(points, dtype=np.float32)
        img_crop_width = int(max(np.linalg.norm(points[0] - points[1]),
                                np.linalg.norm(points[2] - points[3])))
        img_crop_height = int(max(np.linalg.norm(points[0] - points[3]),
                                 np.linalg.norm(points[1] - points[2])))
        
        # 增加边距
        expand_w = int(img_crop_width * expand_ratio)
        expand_h = int(img_crop_height * expand_ratio)
        img_crop_width += expand_w
        img_crop_height += expand_h
        
        # 调整目标点位置以包含边距
        center_x = np.mean(points[:, 0])
        center_y = np.mean(points[:, 1])
        
        # 扩展原始点
        expanded_points = points.copy()
        for i in range(4):
            # 从中心向外扩展
            dx = points[i, 0] - center_x
            dy = points[i, 1] - center_y
            expanded_points[i, 0] = center_x + dx * (1 + expand_ratio)
            expanded_points[i, 1] = center_y + dy * (1 + expand_ratio)
        
        pts_std = np.float32([[0, 0], [img_crop_width, 0],
                             [img_crop_width, img_crop_height],
                             [0, img_crop_height]])

        # 计算透视变换矩阵
        M = cv2.getPerspectiveTransform(expanded_points, pts_std)
        # 执行透视变换
        dst_img = cv2.warpPerspective(img,
                                      M,
                                    (img_crop_width, img_crop_height),
                                    borderMode=cv2.BORDER_REPLICATE,
                                    flags=cv2.INTER_CUBIC)

        # 如果高度大于宽度，旋转90度
        if dst_img.shape[0] * 1.0 / dst_img.shape[1] >= 1.5:
            dst_img = np.rot90(dst_img)
        
        # 提高分辨率（放大图像）
        if upscale_factor > 1.0:
            new_width = int(dst_img.shape[1] * upscale_factor)
            new_height = int(dst_img.shape[0] * upscale_factor)
            dst_img = cv2.resize(dst_img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

        return dst_img

    def crop_text_regions(self, img, dt_boxes):
        """裁剪文本区域"""
        crops = []
        for box in dt_boxes:
            # 确保box是正确的数据类型和形状
            box = np.array(box).astype(np.float32).reshape(-1, 2)
            # 获取裁剪的图像
            crop_img = self.get_rotate_crop_image(img, box)
            crops.append(crop_img)
        return crops

    def recognize_image(self, image_path: str) -> Dict[str, Any]:
        """
        多层级图像识别
        
        Args:
            image_path: 图像路径
            
        Returns:
            识别结果字典，包含text、confidence、method等信息
        """
        result = {
            'text': '',
            'confidence': 0.0,
            'method': 'none',
            'details': []
        }
        
        try:
            # 读取并预处理图片
            img = self.preprocess_image(image_path)
            ori_im = img.copy()
            
            # 第一级：使用自定义检测和识别模型
            try:
                # 文本检测
                dt_boxes, _ = self.custom_detector(img)
                
                if dt_boxes is not None and len(dt_boxes) > 0:
                    logger.info(f"自定义检测器找到 {len(dt_boxes)} 个文本区域")
                    
                    # 裁剪文本区域
                    crops = self.crop_text_regions(img, dt_boxes)
                    
                    # 识别文本
                    for i, crop in enumerate(crops):
                        rec_res, _ = self.custom_recognizer([crop])
                        if rec_res:
                            text, score = rec_res[0]
                            confidence = float(score)
                            
                            # 保存当前结果
                            curr_result = {
                                'text': text,
                                'confidence': confidence,
                                'method': 'custom_model',
                                'details': {'box': dt_boxes[i].tolist(), 'text': text, 'score': confidence}
                            }
                            
                            # 更新置信度更高的结果
                            if curr_result['confidence'] > result['confidence']:
                                result.update(curr_result)
                                logger.info(f"自定义模型识别结果: {text} (置信度: {confidence:.3f})")
                                return result  # 直接返回最高置信度的结果
                else:
                    logger.info("自定义检测器未找到文本区域")
                    
            except Exception as e:
                logger.error(f"自定义模型处理失败: {e}")
            
            # 第二级：使用默认检测和识别模型
            try:
                # 文本检测
                dt_boxes, _ = self.default_detector(img)
                
                if dt_boxes is not None and len(dt_boxes) > 0:
                    logger.info(f"默认检测器找到 {len(dt_boxes)} 个文本区域")
                    
                    # 裁剪文本区域
                    crops = self.crop_text_regions(img, dt_boxes)
                    
                    # 识别文本
                    for i, crop in enumerate(crops):
                        rec_res, _ = self.default_recognizer([crop])
                        if rec_res:
                            text, score = rec_res[0]
                            confidence = float(score)
                            
                            # 保存当前结果
                            curr_result = {
                                'text': text,
                                'confidence': confidence,
                                'method': 'default_model',
                                'details': {'box': dt_boxes[i].tolist(), 'text': text, 'score': confidence}
                            }
                            
                            # 更新置信度更高的结果
                            if curr_result['confidence'] > result['confidence']:
                                result.update(curr_result)
                                logger.info(f"默认模型识别结果: {text} (置信度: {confidence:.3f})")
                                return result  # 直接返回最高置信度的结果
                else:
                    logger.info("默认检测器未找到文本区域")
                    
            except Exception as e:
                logger.error(f"默认模型处理失败: {e}")
            
            # 第三级：API识别
            if self.api_config:
                try:
                    api_result = self._api_recognize(image_path)
                    if api_result:
                        confidence = float(api_result.get('confidence', 0.0))
                        text = api_result.get('text', '')
                        
                        # 保存当前结果
                        curr_result = {
                            'text': text,
                            'confidence': confidence,
                            'method': 'api',
                            'details': api_result.get('details', [])
                        }
                        
                        # 更新置信度更高的结果
                        if curr_result['confidence'] > result['confidence']:
                            result.update(curr_result)
                            logger.info(f"API识别结果: {text} (置信度: {confidence:.3f})")
                            return result  # 直接返回最高置信度的结果
                except Exception as e:
                    logger.error(f"API识别失败: {e}")
            
            # 返回最佳结果（不管是否符合日期格式）
            if result['text']:
                logger.info(f"返回置信度最高的结果: {result['text']} (置信度: {result['confidence']:.3f}, 方法: {result['method']})")
            else:
                logger.warning("未能识别出任何文本")
            return result
            
        except Exception as e:
            logger.error(f"图像处理失败: {e}")
            import traceback
            traceback.print_exc()
            return result
    
    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """从文本中提取第一个日期子串，若无则返回None"""
        date_patterns = [
            r'\d{4}/\d{1,2}/\d{1,2}',
            r'\d{4}-\d{1,2}-\d{1,2}',
            r'\d{4}\.\d{1,2}\.\d{1,2}',
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'生产日期[：:]\s*(\d{4}[\/\.\-年]\d{1,2}[\/\.\-月]\d{1,2}[日]?)',
        ]
        for pattern in date_patterns:
            try:
                m = re.search(pattern, text)
                if m:
                    # 如果是“生产日期：xxxx”的情况，优先返回捕获组内容
                    if m.lastindex:
                        return m.group(1)
                    return m.group(0)
            except re.error:
                continue
        return None

    def _extract_best_date_candidate(self, ocr_data: List[Dict]) -> Optional[Tuple[float, str]]:
        """从每一行结果中筛选最像日期的候选，返回(置信度, 提取到的日期文本)"""
        best: Optional[Tuple[float, str]] = None
        if not ocr_data:
            return None
        for item in ocr_data:
            text = item.get('text', '')
            score = float(item.get('score', 0.0))
            if not text:
                continue
            date_sub = self._extract_date_from_text(text)
            if date_sub:
                if best is None or score > best[0]:
                    best = (score, date_sub)
        return best

    def _process_ocr_result(self, ocr_data: List[Dict]) -> Tuple[float, str]:
        """
        处理OCR识别结果
        
        Args:
            ocr_data: OCR识别的原始数据，格式为：
                [{'box': [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], 
                  'score': float, 
                  'text': str}]
            
        Returns:
            (置信度, 文本) 的元组
        """
        if not ocr_data:
            return 0.0, ""
        
        # 按置信度排序
        sorted_items = sorted(ocr_data, key=lambda x: float(x.get('score', 0)), reverse=True)
        
        # 首先尝试在单个文本框中找到完整的日期格式
        for item in sorted_items:
            text = item.get('text', '')
            score = float(item.get('score', 0))
            if self._validate_date_format(text):
                return score, text
        
        # 如果没找到，尝试合并所有文本并再次检查
        texts = []
        total_score = 0.0
        for item in sorted_items:
            if 'text' in item and 'score' in item:
                texts.append(item['text'])
                total_score += float(item['score'])
        
        combined_text = ' '.join(texts)  # 用空格连接，避免字符粘连
        avg_score = total_score / len(sorted_items) if sorted_items else 0.0
        
        # 如果合并后的文本符合格式要求，返回
        if self._validate_date_format(combined_text):
            return avg_score, combined_text
        
        # 都不符合要求时，返回置信度最高的文本
        if sorted_items:
            best_item = sorted_items[0]
            return float(best_item.get('score', 0)), best_item.get('text', '')
    
    def _validate_date_format(self, text: str) -> bool:
        """
        验证日期格式是否符合要求
        
        Args:
            text: 待验证的文本
            
        Returns:
            是否符合日期格式要求
        """
        # 定义正确的日期格式模式
        patterns = [
            r'生产日期：(\d{4})/(\d{1,2})/(\d{1,2})\s*合格',  # 生产日期：YYYY/MM/DD 合格
            r'生产日期：(\d{4})/(\d{1,2})/(\d{1,2})\s*CH\s*合格',  # 生产日期：YYYY/MM/DD CH 合格
            r'生产日期:(\d{4})/(\d{1,2})/(\d{1,2})\s*合格',  # 生产日期:YYYY/MM/DD 合格
            r'生产日期:(\d{4})/(\d{1,2})/(\d{1,2})\s*CH\s*合格'   # 生产日期:YYYY/MM/DD CH 合格
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                
                # 验证日期的合理性
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return True
        
        return False
    
    def _api_recognize(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        使用API进行识别
        
        Args:
            image_path: 图像路径
            
        Returns:
            API识别结果
        """
        if not self.api_config.get('url'):
            return None
        
        try:
            # 读取图像文件
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # 构建请求
            files = {'image': image_data}
            headers = self.api_config.get('headers', {})
            
            response = requests.post(
                self.api_config['url'],
                files=files,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # 根据实际API响应格式调整
                return {
                    'text': result.get('text', ''),
                    'confidence': result.get('confidence', 0.0),
                    'details': result.get('details', [])
                }
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return None
    
    def batch_recognize(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """
        批量识别图像
        
        Args:
            image_paths: 图像路径列表
            
        Returns:
            识别结果列表
        """
        results = []
        for image_path in image_paths:
            if os.path.exists(image_path):
                result = self.recognize_image(image_path)
                result['image_path'] = image_path
                results.append(result)
            else:
                logger.warning(f"图像文件不存在: {image_path}")
                results.append({
                    'image_path': image_path,
                    'text': '',
                    'confidence': 0.0,
                    'method': 'none',
                    'valid': False,
                    'error': 'file_not_found'
                })
        return results
    
    def get_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取识别统计信息
        
        Args:
            results: 识别结果列表
            
        Returns:
            统计信息字典
        """
        total = len(results)
        if total == 0:
            return {}
        
        method_counts = {}
        confidence_sum = 0.0
        success_count = 0
        
        for result in results:
            method = result.get('method', 'none')
            method_counts[method] = method_counts.get(method, 0) + 1
            
            if result.get('confidence', 0.0) > 0:
                success_count += 1
                confidence_sum += result.get('confidence', 0.0)
        
        return {
            'total': total,
            'success_count': success_count,
            'success_rate': success_count / total * 100,
            'avg_confidence': confidence_sum / success_count if success_count > 0 else 0.0,
            'method_distribution': method_counts
        }
    

def main():
    """主函数 - 示例用法"""
    
    print("=== 多层级OCR系统演示 ===")
    
    # API配置（可选，暂时设为None进行测试）
    api_config = None
    # 如果需要使用API，可以取消注释并配置：
    # api_config = {
    #     'url': 'http://your-api-endpoint.com/ocr',
    #     'headers': {
    #         'Authorization': 'Bearer your-token',
    #         'Content-Type': 'multipart/form-data'
    #     }
    # }
    
    try:
        # 初始化多层级OCR系统
        print("\n初始化OCR系统...")
        ocr_system = MultiLevelOCR(
            api_config=api_config,
            confidence_threshold=0.90
        )
        print("✓ OCR系统初始化完成")
        
        # 创建测试图片目录
        test_dir = os.path.join(os.path.dirname(__file__), "test_images")
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
            print(f"✓ 创建测试目录: {test_dir}")
        
        # 查找测试图片
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        test_images = []
        
        if os.path.exists(test_dir):
            for filename in os.listdir(test_dir):
                if any(filename.lower().endswith(ext) for ext in image_extensions):
                    test_images.append(os.path.join(test_dir, filename))
        
        if not test_images:
            print(f"\n⚠️  未在 {test_dir} 目录下找到测试图片")
            print("请添加一些包含日期信息的图片到该目录下，支持格式：.jpg, .jpeg, .png, .bmp, .tiff")
            return
        
        print(f"\n找到 {len(test_images)} 张测试图片:")
        for img in test_images:
            print(f"  - {os.path.basename(img)}")
        
        # 示例：单张图片识别
        if test_images:
            print(f"\n=== 单张图片识别测试 ===")
            first_image = test_images[0]
            print(f"测试图片: {os.path.basename(first_image)}")
            
            result = ocr_system.recognize_image(first_image)
            print(f"识别结果:")
            print(f"  文本: {result['text']}")
            print(f"  置信度: {result['confidence']:.3f}")
            print(f"  识别方法: {result['method']}")
            if 'details' in result and isinstance(result['details'], dict) and 'box' in result['details']:
                box = result['details']['box']
                print(f"  文本框坐标: {box}")

        # 示例：批量识别
        if len(test_images) > 1:
            print(f"\n=== 批量识别测试 ===")
            batch_results = ocr_system.batch_recognize(test_images)
            
            print(f"批量识别结果:")
            for i, result in enumerate(batch_results, 1):
                img_name = os.path.basename(result['image_path'])
                print(f"  {i}. {img_name}")
                print(f"     文本: {result['text']}")
                print(f"     置信度: {result['confidence']:.3f}")
                print(f"     方法: {result['method']}")
                if 'details' in result and isinstance(result['details'], dict) and 'box' in result['details']:
                    box = result['details']['box']
                    print(f"     文本框坐标: {box}")
            
            # 获取统计信息
            stats = ocr_system.get_statistics(batch_results)
            print(f"\n=== 识别统计 ===")
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        print(f"\n✓ 演示完成")
        
    except Exception as e:
        print(f"❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        if 'ocr_system' in locals():
            del ocr_system


if __name__ == "__main__":
    main()