#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# logging_setup.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260129
# Version: 1.2.0

import sys

def get_logging_config(log_level='INFO'):
    """
    Returns a dictionary with the default logging configuration.
    The log level can be overridden.
    """
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
                'filename': 'logs/app.log',
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
