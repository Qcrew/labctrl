""" """

# THIS IS THE GUI! run an event loop
# 1. load config and / or create new config

from pathlib import Path

import yaml

class StagingError(Exception):
    """ """

def load(configpath: Path) -> list:
    """returns a list of resource objects by reading a YAML file e.g. Instruments"""
    # IO error, attribute error, and bad yaml tag error should be avoided thru careful GUI construction. The only error we have to deal with is if the user selects a BAD configpath (non-yaml file, yaml file with unrecognized tags) to load resources from
    try:
        with open(configpath, mode="r") as config:
            return yaml.safe_load(config)
    except yaml.YAMLError:
        message = f"Failed to identify and load labctrl resources from {configpath}"
        raise StagingError(message) from None
