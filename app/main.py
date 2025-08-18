from __future__ import annotations
import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

# ensure project root is importable
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.core.db import init_db
from app.controllers.app_controller import AppController
from app.core.config import get_resource_path


def main():
    app = QApplication([])
    # Set application icon
    try:
        icon_path = get_resource_path('logo.png')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass
    init_db()
    controller = AppController()
    app.exec()


if __name__ == '__main__':
    main()
