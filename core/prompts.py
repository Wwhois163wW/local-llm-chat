# core/prompts.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.1.1

from typing import Any
import warnings

# --- Prompt 基础块 ---

BASE_ROLE = """You are a powerful AI assistant. 
When communicating, you must follow the ReAct (Reasoning + Acting) paradigm.

### SAFETY & ESCAPING RULES:
1. **XML RESERVED CHARACTERS**: If you need to include a literal '<' character in your text (outside of tool tags), you MUST use '&lt;' to avoid parsing conflicts.
2. **NO UNAUTHORIZED TAGS**: Do not use any XML tags other than the ones explicitly defined in the toolset and ReAct protocol.
3. **NO SPECIAL TOKENS**: Never output tokens like '<|...|>', 'train|>', or any internal channel markers. Your output must be valid plain text or the defined XML tags.
"""

RE_ACT_PROTOCOL = """### ReAct PARADIGM:
For every turn, you MUST structure your response as follows:
1. **Thought**: Start by analyzing the user's request and planning your steps inside <thought> ... </thought> tags.
2. **Action**: If you need to use a tool, wrap the tool call inside <action> ... </action> tags. You can only perform ONE action per turn.
3. **Observation**: (Self-Reminder) You will receive the result of your action as an [Observation] in the next turn.
4. **Final Answer**: Once you have the final information, provide it within <final_answer> ... </final_answer> tags.

### CRUD PERMISSION & SAFETY RULES:
- **DELETE (D)**: Strictly forbidden. You MUST NOT try to delete any file.
- **CREATE (C)**: New file creation is redirected to `.staging/new/`. You cannot overwrite files in staging. **Consecutive Create actions are forbidden**; you must perform at least one non-write action between two creations.
- **UPDATE (U)**: Permitted for the workspace files and staging files. Workspace updates are automatically backed up.
- **READ (R)**: Permitted for workspace files and authorized paths.
"""

FAST_THOUGHT_INSTRUCTION = """
[CRITICAL]: Since this is the first turn of a new task, you MUST perform a 'Fast Thought' check:
- Is there a tool in your toolkit that can directly or indirectly solve this?
- Do you need to probe the file system or system info before answering?
"""

def get_tool_definitions() -> str:
    """Returns the standardized tool definitions for the system prompt."""
    return """<tools>
  <tool>
    <name>get_session_stats</name>
    <description>Gets current session token usage and turn count.</description>
    <usage><get_session_stats /></usage>
  </tool>
  <tool>
    <name>echo</name>
    <description>Sends a final message, confirmation, or summary. Use this to conclude a task or verify connectivity.</description>
    <usage><echo message="Your message here." /></usage>
  </tool>
  <tool>
    <name>write_file</name>
    <description>
      Writes text to a file. 
      - If the file is NEW: It will be created in '.staging/new/'.
      - If the file EXISTS: It will be updated (and backed up if in workspace).
      - [Warning]: Consecutive 'Create' actions are blocked.
    </description>
    <usage><write_file path="filename.ext" content_to_write="...content..." /></usage>
    <observation_example>
      Success: "Successfully wrote to filename.ext"
      Error: "Access denied." or "Disk full."
    </observation_example>
  </tool>
  <tool>
    <name>get_system_info</name>
    <description>Gets OS and environment info.</description>
    <usage><get_system_info /></usage>
    <observation_example>
      Result: "[Observation]: OS: Windows, Python: 3.10.x, CWD: C:\\project"
    </observation_example>
  </tool>
  <tool>
    <name>read_resource</name>
    <description>Reads a slice of a resource. Tip: end="-1" for 100-line preview.</description>
    <usage><read_resource source="res_1" start="1" end="100" /></usage>
    <observation_example>
      Result: "[Observation]: {File Content Snippet}"
      Error: "Resource ID res_1 not found."
    </observation_example>
  </tool>
  <tool>
    <name>search_text</name>
    <description>Searches for a keyword recursively in a directory.</description>
    <usage><search_text path="." query="keyword" /></usage>
    <observation_example>
      Result: "Matches found: file1.py:L10, file2.py:L45"
      Error: "Query too broad."
    </observation_example>
  </tool>
  <tool>
    <name>find_files</name>
    <description>Finds files matching a glob pattern.</description>
    <usage><find_files path="." pattern="*.py" /></usage>
    <observation_example>
      Result: "Found 3 files: main.py, tools.py, session.py"
    </observation_example>
  </tool>
</tools>"""

class AssembledPrompt:
    """
    负责动态拼装系统提示词。
    """
    @staticmethod
    def build(metadata: dict[str, Any]) -> str:
        current_mode = metadata.get("current_mode", "Flush")
        current_task = metadata.get("current_task", "General")
        
        components = [BASE_ROLE]
        
        if current_mode == "ReAct":
            components.append(RE_ACT_PROTOCOL)
            
            # @Antigravity, 20260210, [ADD]: 注入对话历史摘要（长期记忆）
            summary = metadata.get("context_summary")
            if summary:
                components.append(f"\n### PREVIOUS CONTEXT SUMMARY:\n{summary}\n")
            
            components.append(f"\n[CURRENT TASK]: {current_task}")
            # 如果是起始任务（无 meta 记录说明是新任务），注入 Fast Thought
            if metadata.get("is_new_turn", True):
                components.append(FAST_THOUGHT_INSTRUCTION)
        
        components.append("\nAVAILABLE TOOLS:")
        components.append(get_tool_definitions())
        
        return "\n".join(components)

def get_system_prompt() -> str:
    """保持向后兼容的旧入口，内部默认使用空元数据。"""
    # @zhu, 20260210, [MARK] 需要积极更新向后兼容接口
    warnings.warn("get_system_prompt is deprecated, please use AssembledPrompt.build() instead.")
    return AssembledPrompt.build({})

def get_file_injection_prompt(file_name: str, file_content: str) -> str:
    """保持向后兼容。"""
    # @zhu, 20260210, [MARK] 需要积极更新向后兼容接口
    warnings.warn("get_file_injection_prompt is deprecated, please use AssembledPrompt.build() instead.")
    return (
        f"The following is the content of the file '{file_name}', please read it carefully:\n\n"
        f"```\n{file_content}\n```\n"
    )

