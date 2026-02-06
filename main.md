# main.py 伴生文档

## (1) 技术设计要点/总结
- **入口管理**: 负责初始化日志、配置文件和核心依赖（LLM 客户端、会话、代理）。
- **解耦设计**: 通过 `ChatSession` 和 `Agent` 实例的组合，实现了核心调度与业务实现的隔离。
- **环境适应**: 自动创建日志和历史记录目录，确保系统在不同环境下的健壮性。

## (2) 变更记录流水
- **2026.02.06**:
  - **[解耦]**: 移除硬编码，仅保留架构初始化。
  - **[规范]**: 按照用户规则调整命名风格：
    - 函数 `check_history_file` -> `Check_HistoryFile_by_BaseDir`
    - 函数 `main` -> `Main_Process_by_Default`
    - 实例名 `llm_client` -> `llmClient`, `chat_session` -> `chatSession`
  - **[格式]**: 应用长行折行、嵌套调用换行等格式。
