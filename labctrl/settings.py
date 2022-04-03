""" Control global path settings for labctrl """

from pathlib import Path

import yaml

from labctrl.logger import logger

SETTINGSPATH = Path.cwd() / "settings.yml"


class Settings:
    """ 
    How to use:
        settings = Settings()
        settings.<setting> = <value>
        ...
        settings.save()
    Do settings.settings to get a list of all settable <setting> attributes
    """

    def __init__(self) -> None:
        """ """
        with open(SETTINGSPATH, "r") as config:
            settings = yaml.safe_load(config)

        self._keys = settings.keys()

        for name, value in settings.items():
            setattr(self, name, value)
            logger.info(f"Found labctrl setting '{name}' = '{value}'.")

    @property
    def settings(self) -> list[str]:
        """ """
        return sorted(self._keys)

    def save(self) -> None:
        """ """
        settings = {}
        for key in self._keys:
            value = getattr(self, key, None)
            settings[key] = value
        with open(SETTINGSPATH, "w+") as config:
            yaml.safe_dump(settings, config)
