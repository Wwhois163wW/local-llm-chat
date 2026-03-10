#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
# local-llm-chat/tests/test_enricher_logic.py
# Author: ZHU, W. phD

import unittest
import json
import sys
import os
from unittest.mock import MagicMock

# Ensure core is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.processor import LLMProcessor, Get_NMR_Extraction_Prompt

class TestEnricherLogic(unittest.TestCase):
    def setUp(self):
        # We use a mock OpenAI client for logic testing
        self.mock_client = MagicMock()
        self.processor = LLMProcessor(client=self.mock_client, model="qwen")

    def test_prompt_generation_expertise(self):
        """Verify prompt contains NMR technical context via Jinja2."""
        title = "20240501_Polymer_A_zg30_PROJ999"
        messages = Get_NMR_Extraction_Prompt(title)
        
        # Check system message
        system_content = messages[0]['content']
        self.assertIn("NMR data scientist", system_content)
        
        # Check user message (rendered from nmr_extractor.j2)
        user_content = messages[1]['content']
        self.assertIn("Bruker TopSpin", user_content)
        self.assertIn("zg30", user_content)
        self.assertIn(title, user_content)

    def test_logic_separation_simulation(self):
        """
        Verify that we expect LLM to separate pulse programs.
        """
        expected_json = {
            "sample_name": "Polymer_A",
            "project_id": "PROJ999",
            "pulse_program": "zg30"
        }
        
        # Mock the API return
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(expected_json)
        self.mock_client.chat.completions.create.return_value = mock_response

        # Call the processor
        result = self.processor.Extract_JSON_by_Prompt([{"role": "user", "content": "dummy"}])
        
        self.assertEqual(result['sample_name'], "Polymer_A")
        self.assertEqual(result['pulse_program'], "zg30")
        self.assertEqual(result['project_id'], "PROJ999")

if __name__ == '__main__':
    unittest.main()
