""" Our main app is called UHat """

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QAction
from __feature__ import snake_case, true_property

APPNAME = "UHat"


class UHatWindow(QMainWindow):
    """ """

    def __init__(self):
        """ """
        super().__init__()

        self.window_title = APPNAME

        self.menu = self.menu_bar()
        self.stage_menu = self.menu.add_menu("Stage")
        self.measure_menu = self.menu.add_menu("Measure")
        self.settings_menu = self.menu.add_menu("Settings")
        self.help_menu = self.menu.add_menu("Help")

        create_stage = QAction("Create", self)
        create_stage.triggered.connect(self.create_stage)
        self.stage_menu.add_action(create_stage)

        load_stage = QAction("Load", self)
        load_stage.triggered.connect(self.load_stage)
        self.stage_menu.add_action(load_stage)

        teardown_stage = QAction("Teardown", self)
        self.stage_menu.add_action(teardown_stage)

    @Slot()
    def load_stage(self):
        """ """
        filepath = QFileDialog.get_open_file_name(
            parent=self, caption="Select config file", filter="*.yaml *.yml"
        )[0]
        print(filepath)

    @Slot()
    def create_stage(self):
        """ """
        # open stagehand dialog and let it do its thing



if __name__ == "__main__":
    app = QApplication([])
    uhat = UHatWindow()
    uhat.show()
    app.exec()
