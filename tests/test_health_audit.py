#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_health_audit.py
# Author: ZHU, W. phD
# License: RIKEN
# Date: 2026/02/12
# Version: 1.0.0

import unittest
from core.resource_manager import ResourceManager
from core.parser import XmlStreamParser, _PARSER_RULES
from core.events import FileWriteRequest, TextChunk, SpecialTokenDetected

class TestHealthAudit(unittest.TestCase):
    urm: ResourceManager
    parser: XmlStreamParser

    def setUp(self):
        self.urm = ResourceManager(base_dir=".")
        self.parser = XmlStreamParser(_PARSER_RULES)

    def test_urm_deduplication(self):
        """测试 URM 是否能正确去重物理路径。"""
        rid1 = self.urm.register_resource("file", "test.txt", {"size": 100})
        rid2 = self.urm.register_resource("file", "test.txt", {"size": 100})
        
        self.assertEqual(rid1, rid2, "Same file path should result in same RID.")
        self.assertEqual(len(self.urm.resources), 1, "ResourceManager should contain only one entry for same path.")

    def test_parser_nested_lt_violation(self):
        """测试 Parser 在发现嵌套 < 时是否正确触发违规检测（SpecialTokenDetected）。"""
        # 按照新逻辑，这种输入不应被解析，而应报错
        raw_text = '<write_file path="test.txt" content_to_write="<NESTED>" />'
        
        events = list(self.parser.parse_chunk(raw_text))
        events.extend(list(self.parser.flush()))
        
        # 验证是否产出了 SpecialTokenDetected (unexpected_lt_inside_tag)
        special_tokens = [e for e in events if isinstance(e, SpecialTokenDetected) and e.token == "unexpected_lt_inside_tag"]
        self.assertGreaterEqual(len(special_tokens), 1, "Parser failed to detect nested '<' as a violation.")
        
        # 验证没有产生 FileWriteRequest
        write_requests = [e for e in events if isinstance(e, FileWriteRequest)]
        self.assertEqual(len(write_requests), 0, "Parser should not emit FileWriteRequest for nested attribute content.")

    def test_parser_block_style_writing(self):
        """测试基于标签主体的块状写入协议（支持 markdown 剥离）。"""
        raw_text = (
            '<write_file path="test.py">\n'
            '```python\n'
            'print("Hello Block!")\n'
            '```\n'
            '</write_file>'
        )
        
        events = list(self.parser.parse_chunk(raw_text))
        events.extend(list(self.parser.flush()))
        
        write_requests = [e for e in events if isinstance(e, FileWriteRequest)]
        self.assertEqual(len(write_requests), 1)
        self.assertEqual(write_requests[0].path, "test.py")
        # 验证 markdown 剥离
        self.assertEqual(write_requests[0].content_to_write, 'print("Hello Block!")')

    def test_parser_noise_reduction(self):
        """测试 Parser 对普通特殊字符（如 |>）不再产出 unknown token 事件。"""
        # 旧版正则会把 |> 识别为 special_token
        raw_text = "This is some text with |> separator."
        
        events = list(self.parser.parse_chunk(raw_text))
        events.extend(list(self.parser.flush()))
        
        # 验证是否产出了 SpecialTokenDetected
        special_tokens = [e for e in events if isinstance(e, SpecialTokenDetected)]
        self.assertEqual(len(special_tokens), 0, "Parser is still too sensitive to noise like '|>'.")
        
        # 验证正常格式的特殊 Token 仍然能工作
        raw_text_correct = "System is <|READY|>"
        events_correct = list(self.parser.parse_chunk(raw_text_correct))
        events_correct.extend(list(self.parser.flush()))
        
        special_tokens_correct = [e for e in events_correct if isinstance(e, SpecialTokenDetected)]
        self.assertEqual(len(special_tokens_correct), 1)
        self.assertEqual(special_tokens_correct[0].token, "READY")

if __name__ == "__main__":
    unittest.main()
