"""
Abaqus Job Manager — entry point.
"""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# Make sure our package root is importable regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

from app.ui.main_window import MainWindow


def load_stylesheet(app: QApplication) -> None:
    """
    Apply theme.  Prefers qdarkstyle; falls back to our hand-authored QSS.
    """
    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt6"))
        return
    except ImportError:
        pass

    qss_path = Path(__file__).parent / "app" / "styles" / "dark_theme.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Abaqus Job Manager")
    app.setOrganizationName("AbaqusJobManager")
    app.setApplicationDisplayName("Abaqus Job Manager")

    # Enable High-DPI support
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    load_stylesheet(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
