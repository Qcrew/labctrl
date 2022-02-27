""" """

from pathlib import Path

import yaml


class StagingError(Exception):
    """ """


def load(configpath: Path) -> list:
    """returns a list of resource objects by reading a YAML file e.g. Instruments"""
    try:
        with open(configpath, mode="r") as config:
            return yaml.safe_load(config)
    except AttributeError:
        message = (
            f"Failed to load a labctrl resource from {configpath}\n"
            f"An entry in {configpath.name} may have an invalid attribute (key)"
        )
    except yaml.YAMLError:
        message = (
            f"Failed to identify and load labctrl resources from {configpath}\n"
            f"{configpath.name} may have an invalid or unrecognized yaml tag"
        )
        raise StagingError(message) from None
