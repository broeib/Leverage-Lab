"""Centralized logging configuration for the backtesting system."""

import logging
import sys

# Configure a clean console logger
logger = logging.getLogger("LeverageLab")
logger.setLevel(logging.INFO)

# Avoid adding multiple handlers if already configured
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s", 
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
