import sys, os, json
from openai import OpenAI
sys.path.append('local-llm-chat')
from core.processor import LLMProcessor, Get_NMR_Extraction_Prompt, LabKnowledgeMatcher

def test_god_mode():
    matcher = LabKnowledgeMatcher('desk/literature/publications_index.json')
    # Simulate NXY in 2026
    lab_context = matcher.Get_Research_Context('2026', 'NXY')
    print(f"Injected Context: {lab_context}")

    client = OpenAI(base_url='http://192.168.0.200:1234/v1', api_key='lm-studio')
    proc = LLMProcessor(client=client, model='qwen/qwen3-vl-8b')

    prompt = Get_NMR_Extraction_Prompt(
        input_string="20260310 PBS_Sample_New", 
        lab_context=lab_context,
        known_metadata={"solvent": "CDCl3"}
    )
    result = proc.Extract_JSON_by_Prompt(prompt)
    print(f"Result JSON: {json.dumps(result, indent=2, ensure_ascii=False)}")

if __name__ == '__main__':
    test_god_mode()
