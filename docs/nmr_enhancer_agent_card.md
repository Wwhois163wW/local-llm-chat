# Agent Card: NMR Metadata Enhancer (DDD-X2)
基于 Mitchell et al. "Model Cards" 范式与 NMR 行业指南构建

## 1. 代理详情 (Agent Details)
*   **开发信息**: 由 ZHU, W. phD 开发，2026年3月发布。
*   **核心架构**: **DDD (Domain-Driven Design)** 架构。核心组件包括画像师 (PersonaSynthesizer) 与知识匹配器 (KnowledgeMatcher)。
*   **交互模式**: 异步 ReAct 循环，支持批量分块 (Batch Chunking) 执行。
*   **当前版本**: v1.5.0 (Production Stable)。

## 2. 预期用途 (Intended Use)
*   **主要用途**: 自动化解析并结构化 NMR 原始实验标题。提取关键信息（溶剂、脉冲序列、样品浓度、样品名称）。
*   **主要受众**: 实验室自动化平台、合成化学数据管理员。
*   **禁忌用途 (Out-of-scope)**:
    *   **低配环境**: 不建议在 Context Window < 4k 的环境下运行，会导致知识注入失败。
    *   **未定标溶剂**: 若样品使用了 `nmr_kb.json` 之外且未在提示词中定义的极罕见溶剂，提取精度可能下降。

## 3. 环境与影响因素 (Factors)
*   **基建边界 (Infrastructure)**:
    *   **上下文空间**: 8k Tokens (推荐) 用于全量 Persona 注入；4k Tokens 会触发“提示词切除术”导致精度回归。
    *   **硬件加速**: 启用 Flash Attention 与 Q4_0 KV 量化可显著降低延迟。
*   **语义特征 (Semantic Factors)**:
    *   **画像依赖**: 对于命名高度简写（如 `Z-N-1`）的样品，强烈依赖于 `publications_index.json` 中的画像匹配。

## 4. 知识背景与训练 (Knowledge & Integration)
*   **知识库 (KB)**: 集成了常用的 NMR 溶剂（CDCL3, DMSO, D2O 等）与脉冲序列标准名。
*   **画像库 (Persona)**: 包含 ZHU 等核心研究员的历史实验风格与命名拓扑。
*   **治理层 (Governance)**: 所有产出均经过 `GovernanceAdapter` 校验，并强制注入 `$ai:` 前缀以示区别。

## 5. 度量指标 (Metrics)
*   **评估基准**: `benchmark_dataset.json` (20 Cases)。
*   **生产型配置 (8k/T0.1/Flash)**:
    *   **全局准确率**: **100.0%**。
    *   **平均延迟**: **7.9s / record**。
*   **标准型配置 (4k/T0.7)**:
    *   **全局准确率**: 91.4% (存在推理熵引起的轻微抖动)。
    *   **平均延迟**: 15.3s / record。

## 6. 局限性与建议 (Caveats)
*   **局限性**: 代理目前对 1D 数据处理极佳，对复杂 2D/3D 穿透提取尚在试验阶段。
*   **使用建议**: 建议定期更新 `core/knowledge/nmr_kb.json` 以覆盖实验室新购入的化学试剂规格。

---
*Last Updated: 2026-03-13 | License: RIKEN*
