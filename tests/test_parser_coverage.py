#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_parser_coverage.py

import unittest
from typing import cast
from core.parser import XmlStreamParser, _PARSER_RULES
from core.events import (
    ExecuteCommandRequest, ListDirRequest, LoadResourceRequest,
    GetMetadataRequest, FileWriteRequest, TextChunk
)

class TestParserCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = XmlStreamParser(_PARSER_RULES)

    def test_execute_command_parsing(self):
        content = 'I will run a command: <execute_command command="ls -la" cwd="." timeout="10" />'
        events = list(self.parser.parse_chunk(content))
        
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], TextChunk)
        self.assertIsInstance(events[1], ExecuteCommandRequest)
        
        exec_ev = cast(ExecuteCommandRequest, events[1])
        self.assertEqual(exec_ev.command, "ls -la")
        self.assertEqual(exec_ev.cwd, ".")
        self.assertEqual(exec_ev.timeout, 10)

    def test_load_resource_parsing(self):
        content = '<load_resource type="file" source="test.py" />'
        events = list(self.parser.parse_chunk(content))
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], LoadResourceRequest)
        load_ev = cast(LoadResourceRequest, events[0])
        self.assertEqual(load_ev.res_type, "file")
        self.assertEqual(load_ev.source, "test.py")

    def test_list_dir_parsing(self):
        content = 'Checking files: <list_dir path="./infra" />'
        events = list(self.parser.parse_chunk(content))
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[1], ListDirRequest)
        list_ev = cast(ListDirRequest, events[1])
        self.assertEqual(list_ev.path, "./infra")

    def test_get_metadata_parsing(self):
        content = '<get_metadata key="resource:1" />'
        events = list(self.parser.parse_chunk(content))
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], GetMetadataRequest)
        meta_ev = cast(GetMetadataRequest, events[0])
        self.assertEqual(meta_ev.key, "resource:1")

    def test_write_file_cognitive_aligned(self):
        # Even with the new cognitive constraint, the parser just emits the event.
        content = '<write_file path="new.txt" content_to_write="hello" />'
        events = list(self.parser.parse_chunk(content))
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], FileWriteRequest)

if __name__ == "__main__":
    unittest.main()
