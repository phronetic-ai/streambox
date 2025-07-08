import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_handler = RotatingFileHandler(
        f'{current_dir}/app.log',
        maxBytes=50 * 1024 * 1024,
        backupCount=1
    )
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()
