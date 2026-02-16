#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_raw_write.py

import unittest
import asyncio
from typing import Any
from core.parser import parse_stream, XmlStreamParser, _PARSER_RULES
from core.events import FileWriteRequest, TextChunk

class MockStream:
    def __init__(self, chunks):
        self.chunks = chunks
    async def __aiter__(self):
        for chunk in self.chunks:
            # 模拟 OpenAI 流式返回结构
            obj = type('obj', (object,), {
                'choices': [type('obj', (object,), {
                    'delta': type('obj', (object,), {'content': chunk})
                })]
            })
            yield obj

class TestRawWriteProtocol(unittest.TestCase):
    """验证原样写入协议与 OPAQUE 解析模式。"""

    def test_opaque_write_with_xml_tags(self):
        """测试写入包含 XML 标签的内容，验证不再触发 unexpected_lt_inside_tag。"""
        raw_input = (
            '<write_file path="test.html">\n'
            '```html\n'
            '<div>Hello <span class="bold">World</span></div>\n'
            '```\n'
            '</write_file>'
        )
        
        parser = XmlStreamParser(_PARSER_RULES)
        events = list(parser.parse_chunk(raw_input))
        
        # 应该只有一个 FileWriteRequest，不应产生 SpecialTokenDetected
        write_requests = [e for e in events if isinstance(e, FileWriteRequest)]
        self.assertEqual(len(write_requests), 1)
        self.assertIn('<div>Hello <span class="bold">World</span></div>', write_requests[0].content_to_write)

    def test_unicode_multiplication_table(self):
        """测试日志中的九九乘法表特殊符号写入。"""
        raw_input = (
            '<write_file path="nine.py">\n'
            '```python\n'
            'print(f"{j} × {i} = {i*j}")\n'
            '```\n'
            '</write_file>'
        )
        
        parser = XmlStreamParser(_PARSER_RULES)
        events = list(parser.parse_chunk(raw_input))
        
        write_requests = [e for e in events if isinstance(e, FileWriteRequest)]
        self.assertEqual(len(write_requests), 1)
        self.assertIn('×', write_requests[0].content_to_write)

    def test_no_unescape_entity(self):
        """测试禁用 unescape 后，实体字符依然被原样保留。"""
        # 模拟模型输出实体（尽管我们告诉它不要输出，但系统应保持中立）
        raw_input = (
            '<write_file path="entities.txt">\n'
            '```\n'
            'AT&amp;T and <less>\n'
            '```\n'
            '</write_file>'
        )
        
        parser = XmlStreamParser(_PARSER_RULES)
        events = list(parser.parse_chunk(raw_input))
        
        write_requests = [e for e in events if isinstance(e, FileWriteRequest)]
        self.assertEqual(len(write_requests), 1)
        # 验证解析层没有提前做 unescape
        self.assertIn('&amp;', write_requests[0].content_to_write)
        self.assertIn('<less>', write_requests[0].content_to_write)

    def test_multiple_opaque_blocks(self):
        """测试连续两个 OPAQUE 块的定界。"""
        raw_input = (
            '<thought>First thought with <tag></thought>'
            '<write_file path="1.txt">```1```</write_file>'
        )
        parser = XmlStreamParser(_PARSER_RULES)
        events = list(parser.parse_chunk(raw_input))
        
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].__class__.__name__, 'Thought')
        self.assertEqual(events[1].__class__.__name__, 'FileWriteRequest')

if __name__ == '__main__':
    unittest.main()
