#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# parser.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260203
# Version: 1.0.0

import re
import logging
from typing import Generator

from events import TextChunk, FileWriteStart, FileContentChunk, FileWriteEnd, FileReadRequest

logger = logging.getLogger(__name__)

def parse_stream(stream: Generator) -> Generator:
# ...
        while True:
            if not in_file_write_block:
                # Check for read_file first as it's self-closing and simpler
                read_file_match = re.search(r'<read_file path="([^"]+)"\s*/>', buffer)
                if read_file_match:
                    pre_tag_content = buffer[:read_file_match.start()]
                    if pre_tag_content:
                        yield TextChunk(content=pre_tag_content)
                    
                    yield FileReadRequest(path=read_file_match.group(1))
                    
                    buffer = buffer[read_file_match.end():]
                    continue # Continue processing the rest of the buffer

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
                    yield_boundary = buffer.rfind('\n')
                    if yield_boundary != -1:
                        content_to_yield = buffer[:yield_boundary]
                        if content_to_yield:
                            yield TextChunk(content=content_to_yield)
                        buffer = buffer[yield_boundary:]
                    break
            
            if in_file_write_block:
# ...
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
    
                if buffer and not in_file_write_block:
    
                    if buffer:
    
                        yield TextChunk(content=buffer)
    
    
