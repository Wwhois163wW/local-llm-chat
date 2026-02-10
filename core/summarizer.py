#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/summarizer.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.0.0

import logging
from typing import Any
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# @Antigravity, 20260210, [ADD]: 极简摘要提示词，专注于核心连贯性
SUMMARIZER_PROMPT = (
    "You are a conversation analyst. Your task is to summarize the ongoing dialogue. "
    "Focus on:\n"
    "1. USER CORE DEMANDS: What the user explicitly wants to achieve.\n"
    "2. KEY DECISIONS: What actions were taken and what were the outcomes.\n"
    "3. PENDING TASKS: What is currently being worked on or planned.\n\n"
    "Keep it concise, objective, and in bullet points. Use Chinese for the summary."
)

async def Summarize_Conversation_by_LLM(
    client: AsyncOpenAI,
    model: str,
    history: list[dict[str, Any]]
) -> str:
    """
    使用异步 LLM 调用对对话历史进行压缩总结。
    """
    if not history:
        return ""

    try:
        content_to_summarize = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in history 
            if msg['role'] in ['user', 'assistant']
        ])

        # [FIX]: 使用 await 调用异步客户端
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARIZER_PROMPT},
                {"role": "user", "content": f"Please summarize the following history:\n\n{content_to_summarize}"}
            ],
            stream=False
        )
        
        summary = response.choices[0].message.content or ""
        logger.info("[Summarizer] Successfully generated async conversation summary.")
        return summary.strip()
        
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return "Summary failed."
