#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/tools.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.0.3

import os
import logging

logger = logging.getLogger(__name__)

def read_file(base_dir: str, path: str, max_file_size_kb: int, max_output_tokens: int, tokenizer) -> dict:
    """
    Reads a file and returns a result dictionary.
    """
    supported_extensions = ['.txt', '.md', '.py', '.json', '.csv', '.xml', '.html']
    result = {"success": False, "error": "", "content": None}

    try:
        # Security: Prevent path traversal
        safe_base_dir = os.path.abspath(base_dir)
        target_path = os.path.abspath(os.path.join(safe_base_dir, path))
        
        allowed_dirs = [safe_base_dir, os.path.join(safe_base_dir, 'output'), os.path.join(safe_base_dir, 'logs')]
        if not any(target_path.startswith(d) for d in allowed_dirs):
            result["error"] = "Path traversal attempt detected. Access is restricted."
            return result

        _, ext = os.path.splitext(target_path)
        if ext not in supported_extensions:
            result["error"] = f"File type '{ext}' is not supported."
            return result
        
        if not os.path.exists(target_path):
            result["error"] = f"File not found at path '{path}'."
            return result
        
        file_size_kb = os.path.getsize(target_path) / 1024
        if file_size_kb > max_file_size_kb:
             result["error"] = f"File '{os.path.basename(path)}' is too large."
             return result

        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if tokenizer and max_output_tokens > 0:
            encoded_content = tokenizer.encode(content)
            if len(encoded_content) > max_output_tokens:
                truncated_content = tokenizer.decode(encoded_content[:max_output_tokens])
                result["content"] = f"File content is (truncated):\n```\n{truncated_content}\n```"
            else:
                result["content"] = f"File content is:\n```\n{content}\n```"
        else:
            result["content"] = f"File content is:\n```\n{content}\n```"

        result["success"] = True
        return result

    except Exception as e:
        logger.error(f"An unexpected exception occurred in read_file: {e}")
        result["error"] = f"An internal error occurred: {e}"
        return result
