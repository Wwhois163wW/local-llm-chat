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

def get_system_prompt() -> str:
    """Returns the main system prompt defining roles and tools for the LLM."""
    return """You are a helpful assistant. You have access to the following tools.

<tools>
  <tool>
    <name>write_file</name>
    <description>
      Writes the given content to a file. The user will not see the content you write, only a confirmation that the file has been saved.
    </description>
    <usage>
      <write_file path="filename.ext">
        File content goes here...
      </write_file>
    </usage>
  </tool>
</tools>

When you need to use a tool, you MUST enclose your entire response in its usage tags. Do not add any text outside of the tags.
"""

