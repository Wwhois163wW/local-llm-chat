# tools.py 技术说明

## 技术设计要点
- **分级权限 (Tiered CRUD)**: 核心决策逻辑位于 `_is_path_safe`，区分为 Read (R) 与 Write (W) 两种级别。
- **路径重定向**: 恶意或不确定的 Write 操作（如 Create）强制路由至 `.staging/` 影子目录。
- **自动备份**: 对工作区内的 `Update` 操作执行自动带时间戳存底。

## 变更记录流水
- **2026/02/10**: 彻底放开 `list_dir` 权限。修正 `write_file` 路径双重嵌套 Bug。实现异步兼容。
