# core/session_meta.py.md

## 技术设计要点
1. **Pydantic 模型驱动**: 使用 `SessionState` 规范核心元数据（task, mode），提升类型安全性。
2. **审计记录 (Audit Logic)**: 任何元数据变更都会触发 `AuditEntry` 的生成并异步追加至 `.meta_history.jsonl`，确保操作的可追溯性。
3. **元数据隔离**: 区分核心字段与扩展字典（extra），保证架构灵活性。

## 变更记录流水
- **2026/02/10**: 初始化模块。实现基础审计与状态管理。
