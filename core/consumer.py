#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/consumer.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.2

import asyncio
import logging
import configparser
from typing import Any, cast
from dataclasses import asdict
from core.agent import Agent
from core.session import ChatSession
from core.events import TextChunk, StatsUpdate
from infra.background_api import Execute_Task_by_Name

logger = logging.getLogger(__name__)

_SECTION_TITLE = "\n=== AI Agent CLI (Async Turn Architecture) ==="
_SECTION_WELCOME = "Commands: quit, exit, goodbye"

async def consume_events(
    agent: Agent, 
    chat_session: ChatSession, 
    config: configparser.ConfigParser
) -> None:
    """
    运行 Agent 的主交互循环（CLI 界面）。

    Args:
        agent (Agent): 绑定的 Agent 实例。
        chat_session (ChatSession): 当前对话会话对象。
        config (configparser.ConfigParser): 应用程序配置。
    """
    # @Antigravity, 20260206, [CLEANUP]: 移除冗余标注，应用架构收官标准
    print(_SECTION_TITLE)
    print(_SECTION_WELCOME)
    
    # 获取转数限制，架构层只关心控制参数
    max_turns: int = config.getint('Agent', 'max_turns', fallback=3)

    while True:
        try:
            # 1. 用户输入阶段
            user_input: str = await asyncio.to_thread(input, "\nYou > ")
            if user_input.lower() in ["quit", "exit", "goodbye"]:
                break
            
            # 2. 存入内存与磁盘
            chat_session.add_conversation_message('user', user_input)
            
            # 3. 启动 Turn Loop (多轮思考与执行)
            await process_turns(agent, chat_session, max_turns)
            
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            logger.error(f"Error in main interaction loop: {e}", exc_info=True)
            break

async def process_turns(
    agent: Agent, 
    session: ChatSession, 
    max_turns: int
) -> None:
    """
    管理多轮 Agent 思考 (Turn Loop) 及其动作的分发与反馈注入。

    Args:
        agent (Agent): 执行推理的 Agent 实例。
        session (ChatSession): 会话状态容器。
        max_turns (int): 允许的最大递归思维深度。
    """
    turn_count: int = 0
    keep_looping: bool = True
    
    while keep_looping and turn_count < max_turns:
        turn_count += 1
        action_triggered: bool = False
        observations: list[str] = [] # 暂存本轮所有的动作反馈
        
        if turn_count > 1:
            print(
                f"\n[System] 🔄 Turn {turn_count}: "
                f"LLM is re-thinking based on observations..."
            )

        print(f"LLM > ", end="", flush=True)
        
        try:
            # 迭代流事件，基于极简 Agent 直接产出的事件流
            async for event in agent.run():
                # [轨道 A] 即时渲染轨迹
                if isinstance(event, TextChunk):
                    print(event.content, end="", flush=True)
                
                # [轨道 B] 架构动作轨道 (解析流产生的所有非文本、非统计事件)
                elif not isinstance(event, StatsUpdate):
                    action_triggered = True
                    # 动态映射：任务名=类名，参数=asdict
                    task_name: str = type(event).__name__
                    params: dict[str, Any] = asdict(event)
                    
                    obs_result = await handle_generic_action(
                        task_name, 
                        params, 
                        session
                    )
                    if obs_result:
                        observations.append(obs_result)
            
            print() # 视觉换行
            
            # 【时序保证】：在 Assistant 消息记录完成后，统一注入观察结果
            for obs in observations:
                session.Inject_Tool_Observation(obs)
            
            # 只有当触发了动作且有反馈时，才考虑进入下一轮继续思考
            keep_looping = action_triggered
                
        except Exception as e:
            logger.error(f"Error during turn {turn_count}: {e}", exc_info=True)
            break

async def handle_generic_action(
    task_name: str, 
    params: dict[str, Any], 
    session: ChatSession
) -> str | None:
    """
    通用动作分发器。
    将架构层识别出的任务动态转发给 infra 层执行，并处理反馈。

    Args:
        task_name (str): 动态提取的任务/类名。
        params (dict[str, Any]): 动作关联的参数集。
        session (ChatSession): 用于更新状态或注入元数据的会话句柄。

    Returns:
        str | None: 执行结果描述文本（观察结果），如果失败则返回错误提示。
    """
    print(f"\n[System] ⚙️ Executing {task_name}...")
    
    # 转发至基础设施层的总调度函数
    res: dict[str, Any] = await Execute_Task_by_Name(task_name, params)
    
    if not res.get("success"):
        return f"[Error]: Execution of '{task_name}' failed: {res.get('error')}"
    
    # 调度反馈逻辑：
    # 1. 如果 infra 指示需要更新元数据则执行
    metadata_key: str | None = res.get("metadata_key")
    if metadata_key:
        session.Update_Metadata_by_Key(metadata_key, res.get("result"))
    
    # 2. 返回结果以供 consumer 决策是否在下一轮注入历史
    return cast(str | None, res.get("result"))
