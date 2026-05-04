import logging
import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow

logging.basicConfig(
    filename="/tmp/manimator.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    filemode="a",
)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Manimator")
    app.setOrganizationName("manimator")
    app.setApplicationDisplayName("Manimator")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
