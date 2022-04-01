""" Global settings for GUI used across GUI modules"""

from pathlib import Path

import yaml


class Settings:
    """ """

    # path to labctrl settings config file
    _path: Path = Path.cwd() / "settings.yml"

    def __init__(self) -> None:
        """ """
        self._configpath = None
        self._datapath = None
        self._resourcepath = None

        self.update()

    def update(self) -> None:
        """ """
        try:
            with open(Settings._path, "r") as config:
                settings = yaml.safe_load(config)
        except FileNotFoundError:
            pass  # TODO

        for name, value in settings.items():
            setattr(self, f"_{name}", value)

    @property
    def configpath(self) -> Path:
        """ """
        return Path(self._configpath)

    @property
    def datapath(self) -> Path:
        """ """
        return Path(self._datapath)

    @property
    def resourcepath(self) -> Path:
        """ """
        return Path(self._resourcepath)


if __name__ == "__main__":
    s = Settings()
    print(s.__dict__)
