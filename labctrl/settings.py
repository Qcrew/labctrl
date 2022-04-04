""" Control global path settings for labctrl """

from __future__ import annotations

from pathlib import Path

import yaml

from labctrl.logger import logger

# set of all labctrl settings
SETTINGS = {"datapath", "resourcepath"}

SETTINGSPATH = Path(__file__).resolve().parent / "settings.yml"
SETTINGSPATH.touch(exist_ok=True)  # ensure an empty settings.yml always exists
DEFAULT_SETTINGS = dict.fromkeys(SETTINGS)
with open(SETTINGSPATH, "r+") as config:
    if yaml.safe_load(config) is None:
        yaml.safe_dump(DEFAULT_SETTINGS, config)  # ensure default settings always exist

class Settings:
    """ 
    Context manager for settings
    How to use:
    
    with Settings() as settings:
        print(settings)  # to get all labctrl settings that a user can specify
        settings.<setting1> = <value1>  # set 'setting1' to 'value1'
        settings.<setting2> = <value2>  # set 'setting2' to 'value2'
        ...
    """

    def __init__(self) -> None:
        """ """
        with open(SETTINGSPATH, "r") as config:
            self._settings = yaml.safe_load(config)            

        for name, value in self._settings.items():
            setattr(self, name, value)
            logger.debug(f"Found labctrl setting '{name}' = '{value}'.")

    def __repr__(self) -> str:
        """ """
        return f"{self.__class__.__name__} = {SETTINGS}"

    def __enter__(self) -> Settings:
        """ """
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        self.save()

    @property
    def settings(self) -> dict[str, str]:
        """ """
        return {setting: getattr(self, setting) for setting in SETTINGS}

    def save(self) -> None:
        """ """
        settings = self.settings
        logger.debug(f"Saving labctrl settings = {self.settings}...")

        with open(SETTINGSPATH, "w+") as config:
            try:
                yaml.safe_dump(settings, config)
            except yaml.YAMLError as error:
                logger.error(
                    f"Failed to save labctrl settings due to a YAML error:\n"
                    f"Details: {error}"
                    f"Reverted to default settings. Please fix the error and try again."
                )
                yaml.safe_dump(DEFAULT_SETTINGS, config)
