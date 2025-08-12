from __future__ import annotations
from PySide6.QtWidgets import QPushButton, QComboBox, QWidget, QApplication
from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt


def _qcolor_to_rgba(qc: QColor) -> str:
    return f"rgba({qc.red()},{qc.green()},{qc.blue()},{qc.alpha()})"


def set_theme(mode: str = 'auto', root: QWidget | None = None):
    app = QApplication.instance()
    if app is None:
        return
    # Determine dark or light
    dark = False
    if mode == 'dark':
        dark = True
    elif mode == 'light':
        dark = False
    else:  # auto: follow system by palette base color
        base = app.palette().color(QPalette.Base)
        # heuristic: darker bases mean dark theme
        dark = (0.2126 * base.redF() + 0.7152 * base.greenF() + 0.0722 * base.blueF()) < 0.5

    palette = QPalette()
    if dark:
        palette.setColor(QPalette.Window, QColor(32, 32, 32))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(24, 24, 24))
        palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
    else:
        palette.setColor(QPalette.Window, Qt.white)
        palette.setColor(QPalette.WindowText, Qt.black)
        palette.setColor(QPalette.Base, Qt.white)
        palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.Text, Qt.black)
        palette.setColor(QPalette.Button, QColor(245, 245, 245))
        palette.setColor(QPalette.ButtonText, Qt.black)
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)

    # Minimal Fluent-like QSS
    radius = 6
    border = 1
    fg = '#ffffff' if dark else '#000000'
    bg = '#202020' if dark else '#ffffff'
    ctrl_bg = '#2d2d2d' if dark else '#f5f5f5'
    hover = '#333333' if dark else '#e9e9e9'
    press = '#3a3a3a' if dark else '#dddddd'

    qss = f"""
    QWidget {{ background: {bg}; color: {fg}; }}
    QPushButton {{
        background: {ctrl_bg};
        border: {border}px solid rgba(0,0,0,0.08);
        border-radius: {radius}px;
        padding: 6px 12px;
    }}
    /* Secondary buttons: subtle style */
    QPushButton[fluentSecondary="true"] {{
        background: transparent;
        border: {border}px solid rgba(0,0,0,0.10);
    }}
    QPushButton[fluentSecondary="true"]:hover {{ background: {hover}; }}
    QPushButton[fluentSecondary="true"]:pressed {{ background: {press}; }}

    /* Pager emphasis: tweak color for better contrast */
    QPushButton[pager="true"][fluentSecondary="true"] {{
        color: {('#d0e7ff' if dark else '#0b5cad')};
        border-color: rgba(0,120,215,0.35);
    }}
    QPushButton[pager="true"][fluentSecondary="true"]:hover {{
        background: rgba(0,120,215, {0.18 if not dark else 0.22});
    }}
    QPushButton[pager="true"][fluentSecondary="true"]:pressed {{
        background: rgba(0,120,215, {0.28 if not dark else 0.32});
    }}
    QPushButton[pager="true"][fluentPrimary="true"] {{
        /* slightly brighter primary for pager */
        filter: brightness(1.05);
    }}
    QPushButton:hover {{ background: {hover}; }}
    QPushButton:pressed {{ background: {press}; }}
    QComboBox {{
        background: {ctrl_bg};
        border: {border}px solid rgba(0,0,0,0.08);
        border-radius: {radius}px;
        padding: 4px 8px;
    }}
    QComboBox QAbstractItemView {{
        background: {bg};
        selection-background-color: rgba(0, 120, 215, 0.18);
        outline: 0; border: 0;
    }}
    QListWidget {{
        border: {border}px solid rgba(0,0,0,0.06);
        border-radius: {radius}px;
        background: {bg};
    }}
    QSpinBox {{
        background: {ctrl_bg};
        border: {border}px solid rgba(0,0,0,0.08);
        border-radius: {radius}px; padding: 4px 8px;
    }}
    QGraphicsView {{
        border: {border}px solid rgba(0,0,0,0.08);
        border-radius: {radius}px;
        background: {bg};
    }}
    QSplitter::handle {{
        background: rgba(0,0,0,0.04);
        margin: 0px;
    }}
    QMenuBar {{ background: {bg}; }}
    QMenu {{ background: {bg}; border: {border}px solid rgba(0,0,0,0.08); }}
    QMenu::item:selected {{ background: rgba(0,0,0,0.06); }}
    """
    # Apply globally to ensure immediate visual change across all widgets
    app.setStyleSheet(qss)


def set_accent_color(color: QColor, root: QWidget | None = None):
    # Accent only affects PrimaryPushButton for now via dynamic property
    app = QApplication.instance()
    if app is None:
        return
    rgba = _qcolor_to_rgba(color)
    qss = f"""
    QPushButton[fluentPrimary="true"] {{
        background: {rgba}; color: white; border: 0; padding: 6px 12px; border-radius: 6px;
    }}
    QPushButton[fluentPrimary="true"]:hover {{
        background: {rgba};
        opacity: 0.95;
    }}
    QPushButton[fluentPrimary="true"]:pressed {{
        background: {rgba};
        opacity: 0.85;
    }}
    """
    # Append accent styles globally
    app.setStyleSheet((app.styleSheet() or '') + qss)


class PushButton(QPushButton):
    def __init__(self, text: str = '', parent: QWidget | None = None):
        super().__init__(text, parent)


class PrimaryPushButton(QPushButton):
    def __init__(self, text: str = '', parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setProperty('fluentPrimary', True)


class ComboBox(QComboBox):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)


