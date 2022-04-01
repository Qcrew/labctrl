""" GUI to help you create a yaml config file """

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QComboBox,
    QPushButton,
    QCheckBox,
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
from PySide6.QtCore import Qt, Slot

from labctrl import stage
from labctrl.gui.settings import Settings


class StageBuilder(QDialog):
    """ """

    def __init__(self, *args, **kwargs):
        """ """
        super().__init__(*args, **kwargs)

        self.settings = Settings()
        # set of Resource classes
        resource_classes = stage.locate(self.settings.resourcepath)
        self.resource_names = sorted(cls.__name__ for cls in resource_classes)

        self.setWindowTitle("Stage Builder")

        # stage and unstage buttons
        self.button_group_box = QGroupBox()
        self.stage_button = QPushButton("Stage another resource")
        self.stage_button.clicked.connect(self.add_combo_box)
        self.unstage_button = QPushButton("Unstage selected resource(s)")
        self.unstage_button.setEnabled(False)
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
        self.add_combo_box()

        geometry = self.screen().availableGeometry()
        self.setFixedSize(geometry.width() * 0.5, geometry.height() * 0.8)

    @Slot()
    def add_combo_box(self):
        """ """
        combo_box_group = QGroupBox()
        combo_box_group.setFlat(True)
        combo_box = QComboBox()
        combo_box.setPlaceholderText("Select a resource...")
        combo_box.addItems(self.resource_names)
        check_box = QCheckBox()
        combo_box_layout = QHBoxLayout()
        combo_box_layout.setContentsMargins(0, 0, 0, 0)
        combo_box_layout.addWidget(combo_box, 95)
        combo_box_layout.addWidget(check_box, 5)
        combo_box_layout.setAlignment(check_box, Qt.AlignCenter)
        combo_box_group.setLayout(combo_box_layout)

        self.scroll_panel_layout.addWidget(combo_box_group)


if __name__ == "__main__":
    app = QApplication([])
    stagebuilder = StageBuilder()
    stagebuilder.show()
    app.exec()
