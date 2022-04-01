""" Our main app is called UHat """

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QDialog,
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QAction

from labctrl import stage
from labctrl.gui.settings import Settings
from labctrl.gui.stagehand import StageBuilder


class UHat(QMainWindow):
    """ """

    def __init__(self):
        """ """
        super().__init__()

        self.settings = Settings()

        self.resources = None

        self.setWindowTitle("UHat")

        self.menu = self.menuBar()
        self.stage_menu = self.menu.addMenu("Stage")
        self.measure_menu = self.menu.addMenu("Experiments")
        self.settings_menu = self.menu.addMenu("Settings")
        self.help_menu = self.menu.addMenu("Help")

        build_stage = QAction("Build", self)
        build_stage.triggered.connect(self.build_stage)
        self.stage_menu.addAction(build_stage)

        load_stage = QAction("Load", self)
        load_stage.triggered.connect(self.load_stage)
        self.stage_menu.addAction(load_stage)

        teardown_stage = QAction("Teardown", self)
        self.stage_menu.addAction(teardown_stage)

        geometry = self.screen().availableGeometry()
        self.setMinimumSize(geometry.width() * 0.8, geometry.height() * 0.8)
        self.showMaximized()

    @Slot()
    def load_stage(self):
        """ """
        filepath = QFileDialog.getOpenFileName(
            parent=self,
            caption="Select config file",
            dir=str(self.settings.configpath),
            filter="*.yml",
        )[0]
        # self.resources = stage.load(Path(filepath))
        print(filepath)

    @Slot()
    def build_stage(self):
        """ """
        StageBuilder(parent=self).exec()


if __name__ == "__main__":
    app = QApplication([])
    uhat = UHat()
    uhat.show()
    app.exec()
