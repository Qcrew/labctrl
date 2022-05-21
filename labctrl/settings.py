""" Control global settings for labctrl """

from __future__ import annotations

from pathlib import Path

import yaml

from labctrl.logger import logger

SETTINGSPATH = Path.home() / ".labctrl/settings.yml"


def make_default_settings() -> None:
    """ensure default settings always exist"""
    folder = SETTINGSPATH.parent
    folder.mkdir(exist_ok=True)
    SETTINGSPATH.touch(exist_ok=True)
    settings = dict.fromkeys(Settings.__annotations__.keys())
    with open(SETTINGSPATH, "r+") as config:
        yaml.safe_dump(settings, config)


class Settings:
    """
    Context manager for settings
    How to use:
        with Settings() as settings:
            print(settings)  # to get all labctrl settings that a user can specify
            settings.<setting1> = <value1>  # set 'setting1' to 'value1'
            settings.<setting2> = <value2>  # set 'setting2' to 'value2'
            print(settings.settings)  # get latest values of all settings
    Any unrecognized settings found in settings.yml will be ignored
    """

    datapath: str
    resourcepath: str

    def __init__(self) -> None:
        """ """
        if not SETTINGSPATH.exists():
            make_default_settings()

        with SETTINGSPATH.open() as config:
            self._settings = yaml.safe_load(config)

        self._settings_keys = tuple(Settings.__annotations__.keys())
        for name, value in self._settings.items():
            if name in self._settings_keys:
                setattr(self, name, value)

    def __repr__(self) -> None:
        """ """
        return f"{self.__class__.__name__}{self._settings_keys}"

    def __enter__(self) -> Settings:
        """ """
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        self.save()

    @property
    def settings(self) -> dict[str, str]:
        """ """
        return {setting: getattr(self, setting) for setting in self._settings_keys}

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
                default_settings = dict.fromkeys(self._settings_keys)
                yaml.safe_dump(default_settings, config)
