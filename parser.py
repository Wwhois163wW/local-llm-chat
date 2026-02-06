#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# parser.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.1.0

import re
import logging
from events import TextChunk, FileWriteStart, FileContentChunk, FileWriteEnd, FileReadRequest

logger = logging.getLogger(__name__)

async def parse_stream(raw_stream): # Changed to async def
    """
    Parses a raw stream of LLM chunks and yields structured Event objects.
    """
    buffer = ""
    in_file_write_block = False
    
    # raw_stream from the openai client is also an async generator
    async for chunk in raw_stream: # Changed to async for
        content = chunk.choices[0].delta.content or ""
        if not content:
            continue
        buffer += content
        
        # This inner loop for parsing the buffer remains synchronous, which is correct
        while True:
            # ... (the rest of the parsing logic remains the same) ...
            # For example:
            read_file_match = re.search(r'<read_file path="([^"]+)"\s*/>', buffer)
            if read_file_match:
                # ... yield FileReadRequest ...
                buffer = buffer[read_file_match.end():]
                continue
            
            # If no tags are found and buffer can be flushed
            break # Exit inner while loop to get more chunks from async for

    # After the async for loop is exhausted, process any remaining content
    if buffer:
        yield TextChunk(content=buffer)