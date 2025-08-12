from __future__ import annotations
import os
import sys
from PySide6.QtWidgets import QApplication

# ensure project root is importable
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from .core.db import init_db
from .controllers.app_controller import AppController


def main():
    app = QApplication([])
    init_db()
    controller = AppController()
    app.exec()


if __name__ == '__main__':
    main()
