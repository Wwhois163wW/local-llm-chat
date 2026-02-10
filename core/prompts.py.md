# core/prompts.py.md

## 技术设计要点
1. **模块化拼装 (Modular Assembly)**: 放弃硬编码提示词，改用 `AssembledPrompt` 类根据当前 `mode` 和 `task` 动态生成。
2. **ReAct 协议限制**: 明确定义了 `<thought>`, `<action>`, `<final_answer>` 的层级关系，强制 LLM 在思考后才执行。
3. **安全转义规则**: 引入了 `<` 符号转义指南，防止 XML 解析器因内容冲突而崩溃。
4. **Fast Thought 指令**: 为 ReAct 模式转场提供即时激活策略，缩短决策延迟。

## 变更记录流水
- **2026/02/10**: 重写提示词内核。引入 `AssembledPrompt` 与 ReAct 规范。
