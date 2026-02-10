# 中央分发器 (Consumer) 技术文档

## 技术设计要点
- **Turn Loop (多轮思考)**: 实现了一个递归的思维循环，允许 LLM 在执行动作并获得反馈后继续修正其回答，直至进入稳定状态。
- **透明调度 (Transparent Dispatch)**: 核心逻辑不包含任何业务关键词。它通过 `type(event).__name__` 动态识别任务，并通过 `asdict(event)` 提取参数，实现了与具体功能的完全解耦。
- **反馈注入**: 确保所有的“观察结果”（Observations）均在 Assistant 消息完整持久化后才注入 `ChatSession`，保证了对话历史的时序正确性。

## 变更记录流水
- **2026-02-06 (v0.0.1)**:
  - 实现从主循环到 `process_turns` 的迁移。
  - 建立基于 `background_api` 的通用分发链路。
- **2026-02-06 (v0.0.2)**:
  - 彻底清理开发过程中的样式标记。
  - 标准化 Google 风格 Docstring 和类型注解。
  - 增加对 `configparser` 的显式类型支持。
# consumer.md - 事件分发器技术设计与变更记录

## (1) 技术设计要点/总结
- **短路拦截 (Short-circuiting)**: 在 `handle_generic_action` 层优先拦截元数据事件。
- **逻辑闭环**: 元数据不再下放至 `infra` 层，直接在 `core` 内部完成 Session 更新，实现低时延反馈。
- **职责上浮**: 将面向 AI 的“动作反馈字符串”生成逻辑置于此处，保持底层的纯度。

## (2) 变更记录流水
- **2026-02-09 [v0.1.0]**: @Antigravity 实现元数据事件拦截机制，将处理路径从 infra 移回 core。
