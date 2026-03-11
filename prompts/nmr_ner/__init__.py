# core/prompts/nmr_ner/__init__.py
# Prompt Version Controller for NMR Metadata Extraction

PROMPT_VERSIONS = {
    "v1": "nmr_extractor.j2", # Deprecated
    "v2": "v2_dynamic.j2",     # Single record NER
    "v3": "v3_batch_kb.j2"    # NEW: Batch processing + Domain KB Injection
}

# The single source of truth for the active prompt version
CURRENT_VERSION = "v3"

def get_active_template_name():
    return PROMPT_VERSIONS.get(CURRENT_VERSION, "v3_batch_kb.j2")
