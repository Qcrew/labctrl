""" GUI to help you create a yaml config file """

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
)

from labctrl.gui.settings import CONFIGFOLDER

class Stagehand(QDialog):
    """ """

    def __init__(self, *args, **kwargs):
        """ """
        super().__init__(*args, **kwargs)

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
