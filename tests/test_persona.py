# -*- coding: utf-8 -*-
import sys, os, json
sys.path.append('local-llm-chat')
from core.processor import LabKnowledgeMatcher

def test_persona_matching():
    matcher = LabKnowledgeMatcher('desk/literature/publications_index.json')
    
    # Test NXY with 2024 data (should find 2026 papers)
    context = matcher.Get_Research_Context('2024', 'NXY')
    print(f"Synthesized Context (NXY, 2024):")
    print(context)

if __name__ == '__main__':
    test_persona_matching()
