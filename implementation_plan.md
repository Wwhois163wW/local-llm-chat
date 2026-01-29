# 主题：实现对话历史（记忆）功能

**目标**: 将当前单次问答的脚本改造为支持连续对话的交互式应用, 同时内置上下文管理机制, 并确保核心模块可作为独立的API使用。

**设计方案**:

1.  **引入会话状态 (`ChatSession`)**:
    *   在 `chat_module.py` 中, 我们将创建一个 `ChatSession` 类。
    *   这个类将包含一个名为 `history` 的列表属性, 用于存储所有对话记录（格式 `{"role": ..., "content": ...}`）。

2.  **修改 `chat_module.py` (核心模块)**:
    *   `ChatSession` 类将有一个 `send_message` 方法, 此方法是可被外部调用的核心API。
    *   **上下文管理**:
        *   `ChatSession` 在初始化时会从 `config.ini` 读取 `max_history_length` 参数。
        *   `send_message` 方法在发送请求前, 会检查 `history` 列表的长度。如果超出 `max_history_length`, 它会自动裁剪掉**最旧**的对话记录（列表的开头部分）, 以实现一个**滑动窗口**, 防止上下文无限增长。
    *   该方法会接收新的用户输入, 将其与裁剪后的 `history` 整合, 调用LLM API, 然后将用户输入和模型回复都存入`history`中, 最后返回模型的回复字符串。

3.  **修改 `main.py` (交互层)**:
    *   移除 `argparse` 模块, 改为启动一个交互式 `while` 循环, 接收用户在终端的输入。
    *   程序启动时, 实例化一个 `ChatSession` 对象。
    *   在循环中, 调用 `chat_session.send_message()` 方法来处理用户输入并打印回复。
    *   **API优先设计**: 这种设计将交互逻辑 (`main.py`) 与核心对话管理 (`ChatSession`) 彻底分离。`ChatSession` 类本身不处理任何输入输出, 成为一个纯粹的、可复用的模块, 可以被其他任何程序（如图形界面GUI）轻松集成。
    *   增加一个退出机制, 例如, 当用户输入 "quit", "exit" 或 "再见" 时, 退出循环。

4.  **数据流**:
    *   **启动**: `main.py` 初始化 `llm_client` 和 `ChatSession`。
    *   **循环开始**:
        1. `main.py` 等待用户输入。
        2. 用户输入内容。
        3. `main.py` 调用 `chat_session.send_message` 并传入用户输入。
    *   **`ChatSession` 内部 (API核心)**:
        1. 将 `{"role": "user", ...}` 添加到 `history`。
        2. **裁剪 `history` 列表, 确保其不超过 `max_history_length`**。
        3. 将整个 `history` 发送给 LLM API。
        4. 收到回复。
        5. 将 `{"role": "assistant", ...}` 添加到 `history`。
        6. 将回复内容返回给 `main.py`。
    *   **循环结束**: `main.py` 在终端打印回复, 等待下一次输入。

5.  **未来扩展**:
    *   **持久化记忆**: 当前设计使未来在 `ChatSession` 中增加 `save_history()` 和 `load_history()` 方法变得容易, 可实现会话到本地文件的保存和加载。
    *   **高级压缩**: 未来可以探索更智能的压缩策略, 例如用LLM对即将被裁剪掉的旧对话进行总结, 并将摘要保留在上下文中。

**总结**:
这个方案采纳了您的建议, 不仅实现了交互式聊天, 还通过滑动窗口解决了上下文过长的问题, 并保持了核心模块的独立性和可复用性。
