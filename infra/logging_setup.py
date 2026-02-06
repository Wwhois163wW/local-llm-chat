#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/logging_setup.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.2.2

import sys
import os
from typing import Any

def get_logging_config(
    log_dir: str, 
    log_level: str = 'INFO'
) -> dict[str, Any]:
    """
    Returns a dictionary with the default logging configuration.
    The log file path is constructed dynamically based on the provided directory.
    
    Args:
        log_dir (str): The absolute path to the directory where logs should be stored.
        log_level (str): The desired log level for the console handler.
    """
    log_file_path = os.path.join(log_dir, 'app.log')
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simpleFormatter': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'consoleHandler': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'simpleFormatter',
                'stream': sys.stdout,
            },
            'fileHandler': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'simpleFormatter',
                'filename': log_file_path, # Use the absolute path
                'maxBytes': 10485760, # 10MB
                'backupCount': 5,
                'encoding': 'utf8',
            },
        },
        'root': {
            'level': 'DEBUG',
            'handlers': ['consoleHandler', 'fileHandler'],
        },
    }
