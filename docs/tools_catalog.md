# 工具目录 (Tools Catalog)

本文档列出了 EVO-X2 Agent 可调用的所有结构化 XML 命令。

## 1. 资源管理与访问 (URM)
| 标签名称 | 属性 | 功能描述 |
| :--- | :--- | :--- |
| `read_resource` | `source`, `start`, `end` | **多态读取入口**。支持物理路径与 RID 寻址。路径模式下具备自动挂载功能。支持 `end="-1"` 安全预览（100 行）。 |
| `load_resource` | `type`, `source` | **纯探测挂载**。用于大规模文件的前置元数据获取而不进行内容读取。 |
| `list_dir` | `path` | 列出指定目录下的文件与文件夹结构。 |

## 2. 元数据与记忆 (Metadata)
| 标签名称 | 属性 | 功能描述 |
| :--- | :--- | :--- |
| `update_metadata` | `key`, `value`, `persistent` | 更新会话记忆。可选择是否持久化到磁盘（`.meta.json`）。 |
| `get_metadata` | `key` (可选) | 获取全量或特定键名的元数据快照。 |

## 3. 环境与状态探测 (Probing)
| 标签名称 | 属性 | 功能描述 |
| :--- | :--- | :--- |
| `get_cwd` | (无) | 获取当前 Agent 运行的工作目录绝对路径。 |
| `get_system_info` | (无) | 获取宿主机 OS 名称、版本、Python 版本及主机名。 |
| `get_session_stats` | (无) | 获取当前会话的运行时统计（Token 消耗、响应延迟等）。 |

## 4. 其它工具
| 标签名称 | 属性 | 功能描述 |
| :--- | :--- | :--- |
| `echo` | `message` | 用于架构回环验证。返回包含安全性校验词的信息。 |
| `write_file` | `path`, `content_to_write` | 向指定路径写入或覆盖文件内容。 |

---
*注: 所有标签均需使用自闭合格式 `<tag attr="val" />`。*
