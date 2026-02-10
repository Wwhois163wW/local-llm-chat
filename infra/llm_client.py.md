# llm_client.py 技术说明

## 技术设计要点
- **双模支持**: 同时保留同步 `OpenAI` 与异步 `AsyncOpenAI` 实例化方法，确保向后兼容。
- **工厂模式**: 提供 `Get_Async_LLM_Client_by_Config` 统一入口。

## 变更记录流水
- **2026/02/10**: 引入 `AsyncOpenAI` 支持，作为全局异步化改选的核心基础库。
