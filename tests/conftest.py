"""pytest automagics"""
import logging

from libadvian.logging import init_logging


init_logging(logging.DEBUG)
LOGGER = logging.getLogger(__name__)
