#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# parser.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260203
# Version: 1.0.1

import re
import logging
from typing import Generator

from events import TextChunk, FileWriteStart, FileContentChunk, FileWriteEnd, FileReadRequest

logger = logging.getLogger(__name__)

def parse_stream(raw_stream: Generator) -> Generator:
    """
    Parses a raw stream of LLM chunks and yields structured Event objects.
    Implements a state machine to handle tagged language like <write_file> and <read_file>.
    """
    buffer = ""
    in_file_write_block = False # State: True if currently inside a <write_file> tag
    
    for chunk in raw_stream:
        content = chunk.choices[0].delta.content or ""
        if not content:
            continue
        buffer += content
        
        while True:
            # --- Try to parse <read_file> tag ---
            if not in_file_write_block: # Can only look for read_file outside write_file block
                read_file_match = re.search(r'<read_file path="([^"]+)"\s*/>', buffer)
                if read_file_match:
                    pre_tag_content = buffer[:read_file_match.start()]
                    if pre_tag_content:
                        yield TextChunk(content=pre_tag_content)
                    
                    yield FileReadRequest(path=read_file_match.group(1))
                    
                    buffer = buffer[read_file_match.end():]
                    continue # Continue processing the rest of the buffer from current buffer

            # --- Try to parse <write_file> tag ---
            if not in_file_write_block:
                start_tag_match = re.search(r'<write_file path="([^"]+)">', buffer)
                if start_tag_match:
                    pre_tag_content = buffer[:start_tag_match.start()]
                    if pre_tag_content:
                        yield TextChunk(content=pre_tag_content)
                    
                    file_path = start_tag_match.group(1)
                    yield FileWriteStart(path=file_path)
                    
                    buffer = buffer[start_tag_match.end():]
                    in_file_write_block = True
                else:
                    # In normal text mode, yield content line by line or if buffer gets large
                    # to ensure responsiveness, but keep a small tail to avoid splitting a tag.
                    yield_boundary = buffer.rfind('\n')
                    if yield_boundary == -1 and len(buffer) > 100: # Force yield if buffer is large
                        yield_boundary = len(buffer) - 20

                    if yield_boundary != -1:
                        content_to_yield = buffer[:yield_boundary]
                        if content_to_yield:
                            yield TextChunk(content=content_to_yield)
                        buffer = buffer[yield_boundary:]
                    break # Break inner loop to get more chunks
            
            if in_file_write_block:
                end_tag_match = re.search(r'</write_file>', buffer)
                if end_tag_match:
                    file_content_chunk = buffer[:end_tag_match.start()]
                    if file_content_chunk:
                        yield FileContentChunk(content=file_content_chunk)
                    
                    yield FileWriteEnd()
                    
                    buffer = buffer[end_tag_match.end():]
                    in_file_write_block = False
                else:
                    break
        # No more content in buffer to process in this inner loop. Get next chunk.
    
    # After the raw_stream is exhausted, process any remaining content in the buffer
    if buffer:
        if in_file_write_block:
            logger.warning("Stream ended with an unclosed <write_file> tag.")
            yield FileContentChunk(content=buffer) # Yield as file content to main.py to discard
        else:
            if buffer: # Ensure we don't yield empty TextChunk
                yield TextChunk(content=buffer)