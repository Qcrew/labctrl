""" Control global path settings for labctrl """

from __future__ import annotations

from pathlib import Path

import yaml

from labctrl.logger import logger

SETTINGSPATH = Path(__file__).resolve().parent / "settings.yml"


class Settings:
    """ 
    Context manager for settings
    How to use:
    
    with Settings() as settings:
        print(settings.settings)  # to get a list of all available settings
        settings.<setting1> = <value1>
        settings.<setting2> = <value2>
        ...

    The logger will also print all available settings after initializing Settings().
    """

    _settings: set[str] = {"configpath", "datapath", "resourcepath"}

    def __init__(self) -> None:
        """ """
        logger.info(f"Available labctrl settings: {Settings._settings}")

        if SETTINGSPATH.exists():
            with open(SETTINGSPATH, "r") as config:
                settings = yaml.safe_load(config)
        else:
            settings = dict.fromkeys(Settings._settings)  # default settings

        for name, value in settings.items():
            setattr(self, name, value)
            logger.info(f"Found labctrl setting '{name}' = '{value}'.")

    def __enter__(self) -> Settings:
        """ """
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        settings = {}
        for name in Settings._settings:
            value = getattr(self, name, None)
            settings[name] = value
            logger.info(f"Saving labctrl setting '{name}' = '{value}'...")
        
        with open(SETTINGSPATH, "w+") as config:
            try:
                yaml.safe_dump(settings, config)
            except yaml.YAMLError as error:
                logger.error(
                    f"Failed to save labctrl settings due to a YAML error:\n"
                    f"Details: {error}"
                    f"Reverted to default settings. Please fix the error and try again."
                )
                yaml.safe_dump(dict.fromkeys(Settings._settings), config)  # default

    @property
    def settings(self) -> list[str]:
        """ """
        return sorted(Settings._settings)
