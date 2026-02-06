#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/parser.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.1

import re
import logging
from core.events import TextChunk, FileReadRequest

logger = logging.getLogger(__name__)

async def parse_stream(raw_stream): # Changed to async def, but iteration over raw_stream is sync
    """
    Parses a raw stream of LLM chunks and yields structured Event objects.
    """
    buffer = ""
    
    # raw_stream from the openai client is a synchronous iterator, even if the API call was async.
    # So we use a synchronous for loop here.
    for chunk in raw_stream: # Changed back to synchronous for
        content = chunk.choices[0].delta.content or ""
        if not content:
            continue
        buffer += content
        
        while True:
            # ... (the rest of the parsing logic remains the same) ...
            read_file_match = re.search(r'<read_file path="([^"]+)"\s*/>', buffer)
            if read_file_match:
                pre_tag_content = buffer[:read_file_match.start()]
                if pre_tag_content:
                    yield TextChunk(content=pre_tag_content)
                tag_text = read_file_match.group(0)
                yield FileReadRequest(
                    path=read_file_match.group(1), 
                    content=tag_text
                )
                
                buffer = buffer[read_file_match.end():]
                continue

            # Fallback for non-standard read_file format
            alt_read_file_match = re.search(r'<\|channel\|>.*?read_file.*?<\|message\|>.*?{"path":\s*"([^"]+)"\}', buffer, re.DOTALL)
            if alt_read_file_match:
                pre_tag_content = alt_read_file_match.group(1)
                if pre_tag_content:
                    yield TextChunk(content=pre_tag_content)
                
                tag_text = alt_read_file_match.group(0)
                path_from_json = alt_read_file_match.group(3)
                yield FileReadRequest(
                    path=path_from_json, 
                    content=tag_text
                )

                buffer = buffer[alt_read_file_match.end():]
                continue

                buffer = buffer[alt_read_file_match.end():]
                continue

            break # Exit inner while loop to get more chunks
    
    if buffer:
        yield TextChunk(content=buffer)
