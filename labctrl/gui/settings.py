""" Global settings for GUI used across GUI modules"""

from pathlib import Path

# path to folder where user generated config files are saved
CONFIGFOLDER = Path.cwd() / "config"
CONFIGFOLDER.mkdir(exist_ok=True)
