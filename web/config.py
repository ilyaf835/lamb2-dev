import os

from pathlib import Path

from sanic import Config as DefaultConfig
from sanic_ext import Config as DefaultExtentionsConfig


class ExtentionsConfig(DefaultExtentionsConfig):
    HEALTH = False,
    OAS = False
    OAS_AUTODOC = False
    OAS_UI_REDOC = False
    OAS_UI_SWAGGER = False

    TEMPLATING_PATH_TO_TEMPLATES = Path(__file__).parent / 'templates'


class Config(DefaultConfig):
    AUTO_EXTEND = False
    AUTO_RELOAD = False
    ACCESS_LOG = False
    PROXIES_COUNT = 1

    with open(os.environ['SECRET_FILE']) as f:
        SECRET = f.read()
