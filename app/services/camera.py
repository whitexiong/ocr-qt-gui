from __future__ import annotations
import cv2
from PySide6.QtCore import QObject, QThread, Signal


class CameraWorker(QThread):
    frameReady = Signal(object)
    devicesListed = Signal(list)
    error = Signal(str)
    stopped = Signal()

    def __init__(self, device_index: int = 0, width: int = 1280, height: int = 720, parent: QObject | None = None):
        super().__init__(parent)
        self.device_index = device_index
        self.width = width
        self.height = height
        self._running = False
        self.cap = None

    @staticmethod
    def list_devices(max_probe: int = 10):
        # Validate cv2 installation
        if not hasattr(cv2, 'VideoCapture'):
            raise ImportError('未检测到可用的 OpenCV (cv2) VideoCapture，请安装 opencv-python')
        devices = []
        for i in range(max_probe):
            # Prefer DirectShow on Windows, fallback to any
            try:
                backend = getattr(cv2, 'CAP_DSHOW', None)
                cap = cv2.VideoCapture(i, backend) if backend is not None else cv2.VideoCapture(i)
                if cap is not None and cap.isOpened():
                    devices.append((i, f'Camera {i}'))
            finally:
                if 'cap' in locals() and cap:
                    cap.release()
        return devices

    def configure(self, device_index: int, width: int, height: int):
        self.device_index = device_index
        self.width = width
        self.height = height

    def run(self):
        try:
            self._running = True
            if not hasattr(cv2, 'VideoCapture'):
                self.error.emit('OpenCV (opencv-python) 未安装或不完整，无法打开相机')
                return
            backend = getattr(cv2, 'CAP_DSHOW', None)
            self.cap = cv2.VideoCapture(self.device_index, backend) if backend is not None else cv2.VideoCapture(self.device_index)
            if not self.cap or not self.cap.isOpened():
                self.error.emit('无法打开相机')
                return
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            while self._running:
                ok, frame = self.cap.read()
                if not ok:
                    continue
                self.frameReady.emit(frame)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if self.cap:
                self.cap.release()

    def stop(self):
        self._running = False
        self.wait(1000)
        self.stopped.emit()


