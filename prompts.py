#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# prompts.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260130
# Version: 1.0.0

def get_file_injection_prompt(file_name: str, file_content: str) -> str:
    """Returns the default prompt for injecting file content into the context."""
    return (
        f"The following is the content of the file '{file_name}', please read it carefully:\n\n"
        f"```\n{file_content}\n```\n\n"
        f"Once read, you can proceed with the user's main query."
    )

