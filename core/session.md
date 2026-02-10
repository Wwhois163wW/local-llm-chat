# core/session.py 伴生文档

## (1) 技术设计要点/总结
- **会话持久化**: 采用 JSONL 格式高效处理流式消息的追加与读取。
- **Token 感知**: 接入 Tiktoken 实现精确的 Token 计算，为上下文控制提供量化依据。
- **架构反馈接口**: 显式定义 `Inject_Tool_Observation` 和 `Update_Metadata_by_Key` 方法，作为外部调度器（Consumer）与内部状态间的通信桥梁。
- **角色注入策略**: 将工具观察结果从 `system` 角色改为 `user` 角色注入（前缀 `[Observation]:`），显著提升了 LLM 对实时环境反馈的感知灵敏度。

## (2) 变更记录流水
- **2026.02.06**:
  - **[标准]**: 按照 Google 规范补全 `ChatSession` 类及其所有方法的 Docstring。
  - **[规范]**: 补全所有 `dict` 和 `list` 的泛型参数说明，显式初始化消息缓冲区。
  - **[修复]**: 修正了 `_load_conversation_memory_from_file` 逻辑，确保 `system` 角色消息（包含工具反馈）能被正确反序列化，解决会话断点记忆丢失问题。
  - **[修复]**: 处理了文件写入返回值未使用的 lint 警告。
  - **[格式]**: 深度对齐长行折行、嵌套调用换行等排版规范。
- **双层存储架构**: 实现了 `transient_meta` (内存) 与 `persistent_meta` (磁盘) 的物理分离。
- **持久化驱动**: 在更新标记为 `persistent=True` 的键值时，会自动触发对 `{history_file}.meta.json` 的异步/同步写入。
- **数据一致性**: 内存态数据在合并时始终覆盖持久态同名键（`{**persistent, **transient}`）。
- **接口标准化**: 提供了语义化的 `Update_Metadata_by_Key` 和 `get_metadata` (合并字典) 接口。

## (2) 变更记录流水
- **2026-02-09 [v0.1.0]**: @Antigravity 引入基础元数据内核。
- **2026-02-09 [v0.1.1]**: @Antigravity 补充 `get_metadata` 字典合并方法，优化提示词注入逻辑。
- **2026-02-09 [v0.1.2]**: @Antigravity 移除重复的 `Get_Metadata_Snapshot` 描述逻辑，实现 core 层逻辑净化。