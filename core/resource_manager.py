# core/resource_manager.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260216
# Version: 1.2.0

import logging
import re
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

class ResourceManager:
    """
    统一资源管理器 (URM) 的核心组件。
    负责维护会话生命周期内的对话要素（Path/URL/Block）映射。
    """
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.resources: dict[str, dict[str, Any]] = {}
        # 反向映射：内容 -> RID，用于去重
        self.content_to_rid: dict[str, str] = {}
        # 各分类计数器
        self.counters = {
            "path": 1,
            "url": 1,
            "block": 1
        }
        logger.info(f"ResourceManager 2.0 initialized. Middleware mode active.")

    def register_resource(self, category: str, content: str, metadata: dict[str, Any]) -> str:
        """
        按分类注册一个资源别名。
        """
        if content in self.content_to_rid:
            return self.content_to_rid[content]

        if category not in self.counters:
            category = "path" # 默认降级

        rid = f"{category}_{self.counters[category]}"
        self.resources[rid] = {
            "category": category,
            "content": content,
            "metadata": metadata,
            "timestamp": time.time()
        }
        self.content_to_rid[content] = rid
        self.counters[category] += 1
        logger.info(f"[URM] Registered {rid} for {category}: {content[:30]}...")
        return rid

    def probe_elements(self, text: str) -> list[str]:
        """
        [PROACTIVE]: 扫描文本中的路径、URL 和代码块。
        """
        detected_rids = []
        
        # 1. 探测 Markdown 代码块
        # 捕获 ```lang ... ``` 结构
        block_pattern = r'```(?:[a-zA-Z0-9]*)\n([\s\S]*?)\n```'
        blocks = re.findall(block_pattern, text)
        for b in blocks:
            if len(b.strip()) > 10: # 仅记录有意义的长文本块
                rid = self.register_resource("block", b.strip(), {"source": "assistant_msg" if "@Antigravity" in text else "user_msg"})
                detected_rids.append(rid)

        # 2. 探测 URL
        url_pattern = r'https?://[^\s<>"]+|ftp://[^\s<>"]+'
        urls = re.findall(url_pattern, text)
        for u in urls:
            u = u.rstrip('.,;)]}!')
            rid = self.register_resource("url", u, {"found_by": "regex_probe"})
            detected_rids.append(rid)

        # 3. 探测 路径/文件名
        # 兼容性增强版正则
        path_pattern = r'(?:[a-zA-Z]:[\\/][^ \s"\'<>|]+|(?:\.\.?[\\/])?[^ \s"\'<>|]+[\\/][^ \s"\'<>|]+|[\w\.\-\u4e00-\u9fa5]+\.[a-zA-Z0-9]+)'
        paths = re.findall(path_pattern, text)
        
        # 补充：对包含层级的相对路径进行兜底探测
        greedy_paths = re.findall(r'[\w\.\-\u4e00-\u9fa5/\\\_]+\.[a-zA-Z0-9]+', text)
        paths.extend(greedy_paths)
        
        for p in list(set(paths)):
            if '/' not in p and '\\' not in p and '.' not in p: continue
            p = p.strip('.,;)]}!" \'')
            # 校验物理存在性
            full_path = p if os.path.isabs(p) else os.path.abspath(os.path.join(self.base_dir, p))
            if os.path.exists(full_path) and os.path.isfile(full_path):
                rid = self.register_resource("path", p, {"found_by": "file_probe"})
                detected_rids.append(rid)
        
        return list(set(detected_rids))

    def get_resource(self, rid: str) -> dict[str, Any] | None:
        return self.resources.get(rid)

    def get_resource_description(self, rid: str) -> str:
        res = self.get_resource(rid)
        if not res: return f"ID {rid} not found."
        
        cat = res["category"]
        content = res["content"]
        
        if cat == "block":
            snippet = content[:50].replace('\n', ' ') + "..."
            return f"[CodeBlock] {snippet} -> ID: {rid}"
        elif cat == "path":
            return f"[Path] {content} -> ID: {rid}"
        elif cat == "url":
            return f"[Link] {content} -> ID: {rid}"
            
        return f"[{cat.upper()}] {content[:30]} -> ID: {rid}"

    def clear(self):
        self.resources.clear()
        self.content_to_rid.clear()
        for k in self.counters: self.counters[k] = 1
