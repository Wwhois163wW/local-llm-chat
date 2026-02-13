import os
import warnings
from typing import Any
from jinja2 import Environment, FileSystemLoader

# core/prompts.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260213
# Version: 2.1.1

# --- 动态工具注册表 (TOOL_REGISTRY) ---
# 每个工具包含核心定义与适用角色标签
# 'all' 标签仅限于所有机器人必须具备的基础感知/诊断工具
TOOL_REGISTRY = [
    {
        "name": "load_resource",
        "description": "Probes file metadata and creates a proactive backup in staging/backups/. Effectively 'Loads' the file into your cognitive scope for future updates.",
        "usage": '<load_resource type="file" source="path/to/file.ext" />',
        "tags": ["coder", "researcher"]
    },
    {
        "name": "read_resource",
        "description": "Reads a slice of a resource. Tip: end='-1' for 100-line preview. Automatically Loads the resource if not already known.",
        "usage": '<read_resource source="res_1_or_path" start="1" end="100" />',
        "tags": ["coder", "researcher"]
    },
    {
        "name": "write_file",
        "description": "Writes text to a file. Redirects to staging/new/ if NOT already Loaded/Known. Backs up if updating known workspace files. Put content inside the tag body wrapped in ```.",
        "usage": '<write_file path="filename.ext">\n```\nContent here...\n```\n</write_file>',
        "tags": ["coder"]
    },
    {
        "name": "list_dir",
        "description": "Lists contents of a directory. Use this to explore the workspace structure.",
        "usage": '<list_dir path="." />',
        "tags": ["coder", "researcher"]
    },
    {
        "name": "find_files",
        "description": "Finds files matching a glob pattern (e.g., *.py).",
        "usage": '<find_files path="." pattern="*.py" />',
        "tags": ["coder", "researcher"]
    },
    {
        "name": "search_text",
        "description": "Searches for keywords recursively in text files.",
        "usage": '<search_text path="." query="keyword" />',
        "tags": ["coder", "researcher"]
    },
    {
        "name": "execute_command",
        "description": "Executes a shell command. Requires HUMAN APPROVAL. Use sparingly for environment checks or build tasks.",
        "usage": '<execute_command command="pip list" cwd="." timeout="30" />',
        "tags": ["coder"]
    },
    {
        "name": "get_metadata",
        "description": "Retrieves a snapshot of all session/resource metadata. Supports nested keys like 'resource:1.metadata'.",
        "usage": '<get_metadata key="optional_key" />',
        "tags": ["profiler", "manager"]
    },
    {
        "name": "update_metadata",
        "description": "Sets a metadata key in the current session. Set persistent='true' for cross-session memory.",
        "usage": '<update_metadata key="k" value="v" persistent="false" />',
        "tags": ["profiler", "manager"]
    },
    {
        "name": "get_system_info",
        "description": "Gets OS and environment status.",
        "usage": '<get_system_info />',
        "tags": ["all"]
    },
    {
        "name": "get_session_stats",
        "description": "Gets current token usage and turn count.",
        "usage": '<get_session_stats />',
        "tags": ["manager"]
    },
    {
        "name": "get_cwd",
        "description": "Gets current working directory.",
        "usage": '<get_cwd />',
        "tags": ["coder", "researcher"]
    }
]

class AssembledPrompt:
    """
    负责使用 Jinja2 引擎动态拼装提示词。
    模板存储在同级目录下的 prompts/ 文件夹中。
    """
    _env: Environment | None = None

    @classmethod
    def _get_env(cls) -> Environment:
        """初始化并缓存 Jinja2 环境。"""
        if cls._env is None:
            template_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "prompts"
            )
            cls._env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=False,
                trim_blocks=False,
                lstrip_blocks=False
            )
        return cls._env

    @staticmethod
    def build(metadata: dict[str, Any]) -> str:
        """
        基于元数据渲染系统提示词总线模板。
        支持基于当前角色的动态工具组装。
        """
        try:
            env = AssembledPrompt._get_env()
            template = env.get_template("system_prompt.j2")
            
            # 动态工具组装逻辑
            current_role = metadata.get("current_role", "all")
            if current_role == "all":
                tools = TOOL_REGISTRY
            else:
                tools = [
                    t for t in TOOL_REGISTRY 
                    if current_role in t["tags"] or "all" in t["tags"]
                ]

            # 准备渲染上下文
            context = {
                "metadata": metadata,
                "current_mode": metadata.get("current_mode", "ReAct"),
                "current_role": current_role,
                "current_task": metadata.get("current_task", "General Task"),
                "context_summary": metadata.get("context_summary"),
                "user_profile": metadata.get("user_profile"),
                "is_new_turn": metadata.get("is_new_turn", True),
                "tools": tools
            }
            
            return template.render(**context)
        except Exception as e:
            return f"Error: Failed to render system prompt. Reason: {e}"

def get_system_prompt() -> str:
    """保持向后兼容的旧入口。"""
    warnings.warn("get_system_prompt is deprecated, please use AssembledPrompt.build() instead.")
    return AssembledPrompt.build({})

def get_file_injection_prompt(file_name: str, file_content: str) -> str:
    """保持向后兼容。"""
    warnings.warn("get_file_injection_prompt is deprecated, please use AssembledPrompt.build() instead.")
    return (
        f"The following is the content of the file '{file_name}', please read it carefully:\n\n"
        f"```\n{file_content}\n```\n"
    )
