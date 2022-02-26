""" GUI to help you create a yaml config file """

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QComboBox,
    QPushButton,
    QVBoxLayout,
    QButtonGroup,
    QApplication,
    QScrollArea,
    QGridLayout,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QLineEdit,
    QDialog,
)
from PySide6.QtCore import Qt

from labctrl.gui.settings import CONFIGFOLDER


class StageBuilder(QDialog):
    """ """

    def __init__(self, *args, **kwargs):
        """ """
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Stage Builder")

        # stage and unstage buttons
        self.button_group_box = QGroupBox()
        self.stage_button = QPushButton("Stage another resource")
        self.unstage_button = QPushButton("Unstage selected resource(s)")
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.addWidget(self.stage_button)
        self.buttons_layout.addWidget(self.unstage_button)
        self.button_group_box.setLayout(self.buttons_layout)

        # filename entry widget
        self.filename_group_box = QGroupBox()
        self.filename_label = QLabel("Filename:")
        self.filename_edit = QLineEdit()
        self.filename_layout = QHBoxLayout()
        self.filename_layout.addWidget(self.filename_label)
        self.filename_layout.addWidget(self.filename_edit)
        self.filename_group_box.setLayout(self.filename_layout)

        # connect button
        self.connect_button = QPushButton("Connect")

        # scroll widgets
        self.scroll_panel = QWidget()
        self.scroll_panel_layout = QFormLayout(self.scroll_panel)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(self.scroll_panel)

        # main layout
        self.main_layout = QGridLayout(self)
        self.main_layout.addWidget(self.button_group_box)
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addWidget(self.filename_group_box)
        self.main_layout.addWidget(self.connect_button)

        # add nominal combo box (1st resource to be staged)
        self.resource_selector = QComboBox()
        self.scroll_panel_layout.addWidget(self.resource_selector)

        # add a central 'add' button that shows a combo box below (list)
        # combo box which shows available resource classes you can add to config
        # how to retrieve resource classes ?
        # once object selected in combo box show its params below... how to get these?
        # user fills values, adds more resources if needed,
        # once compulsory ones are filled, allow them to click DONE and exit dialog
        # how to know when compulsory values are filled ??
        # basically, how to do form input validation ??
        # exiting dialog automatically saves file in configfolder if input is valid
        # caveat: need instrument connected to PC in order to create and save the config
        # if input is invalid, dialog will inform user
        # this should be a modal dialog as it is separate from the main app

        geometry = self.screen().availableGeometry()
        self.setFixedSize(geometry.width() * 0.5, geometry.height() * 0.8)


if __name__ == "__main__":
    app = QApplication([])
    stagebuilder = StageBuilder()
    stagebuilder.show()
    app.exec()
