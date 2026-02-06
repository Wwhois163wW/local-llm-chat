# main.py (Entry Point)

## 1. 技术设计要点/总结
*   **功能**: 作为系统的入口，负责加载配置、初始化各层模块、并启动事件消费循环。
*   **分层协调**: 
    *   通过 `infra/logging_setup.py` 配置全局日志。
    *   通过 `infra/llm_client.py` 获取 LLM 客户端。
    *   初始化 `core/session.py` (ChatSession) 和 `core/agent.py` (Agent)。
    *   将逻辑委托给 `core/consumer.py` 启动最终的任务循环。
*   **启动流**:
    1. 加载 `config.ini`。
    2. 设置输出目录 (output/) 和日志。
    3. 构建 Agent 实例。
    4. 进入 `consume_events` 阻塞直到退出。

## 2. 变更记录流水
*   **20260206, [REFACTOR]: 架构分层重构**: 
    *   将原本臃肿的 `main.py` 逻辑拆分，核心交互循环移至 `core/consumer.py`。
    *   引入 `core/` 和 `infra/` 结构，`main.py` 现在仅负责顶层的启动器 (Starter) 职责。
    *   修正了所有模块的导入路径。

*   **20260130, [REFACTOR]: 简化/add指令处理**: 将文件读取和Prompt包装逻辑从 `main.py` 移除，转为直接调用 `chat_session.send_message` 的 `files` 参数，使 `main.py` 更专注于用户交互。
*   **20260129, [FIX]: 优化路径解析**: 为 `/add` 指令增加了自动剥离首尾引号的功能，方便直接粘贴 Windows 的“复制为路径”结果。

*   **20260129, [ADD]: 实现文件注入功能**: 增加了 `/add` 指令处理逻辑，支持读取 UTF-8 文本文件并将其内容作为上下文发送给 LLM。
*   **20260129, [MOD]: 更新退出指令**: 移除中文退出指令 "再见", 并增加英文指令 "goodbye"。
*   **20260129, [ADD]: 优化UX与持久化**: 引入多线程机制实现 "Thinking..." 加载动画，并增加 CSV 日志记录功能，将使用数据保存至 `usage_stats.csv`。
*   **20260129, [ADD]: 增加统计数据展示**: 更新了交互循环, 以美化的格式实时展示响应延迟和 token 使用情况 (输入/输出/总量)。
*   **20260129, [REFACTOR]: 实现交互式循环**: 移除了 `argparse` 命令行解析, 改为使用 `while` 循环来接收用户连续输入, 将程序从一次性脚本转变为交互式应用。
*   **20260129, [MOD]: 集成ChatSession**: 更新了 `main` 函数, 以便初始化并使用 `ChatSession` 类来管理整个对话生命周期。
*   **20260127, [ADD]: 创建文件**: 根据重构计划, 创建主程序入口。
