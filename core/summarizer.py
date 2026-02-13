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

# @Antigravity, 20260212, [ADD]: 语义提取提示词，用于优化工具观测值的注入密度
EXTRACTOR_PROMPT = (
    "You are an Information Density Optimizer. Your task is to extract the core information from a tool's output. "
    "Focus on:\n"
    "1. CRITICAL DATA: Errors, success indicators, or unique identifiers.\n"
    "2. STRUCTURE: Function signatures, file lists, or schema outlines.\n"
    "3. TRUNCATION: Remove redundant lines, boilerplate, or repetitive content.\n\n"
    "Your output will be used as a ReAct [Observation]. Keep it extremely concise and technical. "
    "Do NOT change the original semantic meaning. Use English for technical extraction."
)

async def Extract_Key_Info_by_LLM(
    client: AsyncOpenAI,
    model: str,
    raw_content: str
) -> str:
    """
    对超长工具输出执行语义提取，优化注入 Context 的密度。
    """
    if not raw_content or len(raw_content) < 500:
        return raw_content

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTOR_PROMPT},
                {"role": "user", "content": f"Extract key info from this raw output:\n\n{raw_content}"}
            ],
            stream=False
        )
        summary = response.choices[0].message.content or "Extraction failed."
        logger.info("[Summarizer] Successfully optimized tool observation density.")
        return f"[Summarized Observation]: {summary.strip()}\n(Note: Original content was truncated for efficiency.)"
        
    except Exception as e:
        logger.error(f"Failed to extract key info: {e}")
        return f"[Observation (Partial)]: {raw_content[:500]}... [Truncated due to error]"

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
