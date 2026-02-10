# core/prompts.md

## 1. 技术设计要点/总结
*   **职责**: 集中管理各种 LLM 提示词模板。
*   **System Prompt**: 定义了 AI 的角色设定、已知工具的使用范式以及输出约束，确保其符合“智能助手”的行为预期。

## 2. 变更记录流水
*   **20260206, [REFACTOR]: 架构重构迁移**: 物理搬迁至 `core/` 目录。
## (1) 技术设计要点/总结
- **工具认知注入**: 在 System Prompt 中同步增加了对 `update_metadata` 和 `get_metadata` 的 XML 规范描述。
- **格式硬约束**: 为解决模型倾向于使用外部指令格式（如 `<|channel|>`）的问题，引入了显式的格式禁令说明。

## (2) 变更记录流水
- **2026-02-09 [v1.0.2]**: @Antigravity 注入元数据工具说明并强化 XML 格式约束。
- **2026-02-10 [v1.0.3]**: @Antigravity 正式声明 `get_cwd` 和 `get_system_info` 探测工具。
- **2026-02-10 [v1.1.0]**: @Antigravity 开启 URM 工具集 (`load_resource`, `inject_resource`)，引导 AI 进入“探测-分片”模式。
- **2026-02-10 [v1.2.0]**: @Antigravity 统一读取协议：废弃 `inject_resource` 和 `read_file`，全面推行自适应 `read_resource`。
