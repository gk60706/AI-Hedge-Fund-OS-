# V3.9.3 断点续跑（Checkpoint / Restore / Resume）

本文档说明 `evolution/alpha_evolution.py` 的 checkpoint 能力，以及续跑等价性的实测证据。

## 1. 能力

| 接口 | 说明 |
| --- | --- |
| `engine.export_state() -> dict` | 导出完整状态：配置、种群、RNG、代际报告、fitness 结果、运行元数据、早停计数器、历史 `run_id` / `history_config`、`created_at`。非有限浮点（NaN / -inf）统一转为 `null`，确保 `json.dumps(allow_nan=False)` 可通过。 |
| `engine.save_checkpoint(path) -> Path` | 原子写盘：`mkstemp` 同目录临时文件 → `flush` + `fsync` → `os.replace`；失败清理临时文件并抛 `CheckpointError`。 |
| `engine.restore_state(state)` | 先全量校验（版本、实验名、配置、种群、RNG、报告、fitness、计数器），全部通过后才替换现有状态；任何结构性错误转 `CheckpointCorruptionError`，不会留下半恢复对象。 |
| `AlphaEvolutionEngine.from_checkpoint(path, *, research_evaluator=None, fitness_evaluator=None, history=None, strict=True)` | 读取文件 → 版本校验 → 由 checkpoint 内的 `history_config` / `history_run_id` 重建 `EvolutionHistory`（否则历史按 `run_id` 过滤会读不到记录）→ `restore_state` → 与 JSONL 最新代际比对。 |
| `FitnessResult.from_dict(data)` | 必填 `genome_id` / `fitness` / `valid`；未知字段丢弃；bool、有限数值、字符串列表、`details` 逐项校验。 |

异常层级：

```
AlphaEvolutionError
└── CheckpointError
    ├── CheckpointVersionError      # schema_version 不是 3.9.3
    ├── CheckpointCorruptionError   # 缺字段 / 类型错 / JSON 坏 / 配置不一致
    └── CheckpointConsistencyError  # checkpoint 与 JSONL 历史代际不一致（strict）
```

## 2. 一致性校验

`from_checkpoint` 会读取该 `run_id` 下最后一条 `generation` 记录，与 `population.generation` 比较：

- `strict=True`（默认）：不一致抛 `CheckpointConsistencyError`；
- `strict=False`：写入 `run_metadata["checkpoint_history_mismatch"]` 后继续，便于事后审计；
- 历史文件里没有记录：写入 `run_metadata["checkpoint_history_records_missing"] = True`；
- 读取历史本身失败：strict 抛错，非 strict 写入 `run_metadata["checkpoint_history_check_error"]`。

## 3. 一个必须知道的坑：RNG 不止一个

`AlphaPopulation` 内部有 **4 个独立随机源**：

| 位置 | 属性 | 用途 |
| --- | --- | --- |
| `population` | `_rng` | 决定 crossover / mutation、`select_parent` |
| `mutation_engine` | `rng` | 变异算子内部选点 |
| `crossover_engine` | `rng` | 交叉点选择 |
| `generator` | `random` | 随机移民个体生成 |

只恢复 `population._rng` 会出现「代数一致、最佳 fitness 不一致」的假续跑（实测 0.975 vs 0.901）。因此 checkpoint 额外保存 `component_rng_states`（上述四者 `getstate()` 的 JSON 化列表），恢复时逐一 `setstate()`；任何 checkpoint 里出现未知组件名会直接判为损坏，避免静默降级。

## 4. 测试

`evolution/test_v393_checkpoint.py`：

- `test_checkpoint_resume_matches_uninterrupted_run`：中断在 gen1 后 checkpoint，续跑 2 代，与不中断跑 4 代比对代际、最佳 fitness、后续 RNG 抽样序列、报告代际 `[0,1,2,3]`；
- `test_checkpoint_state_is_json_safe_and_contains_rng`：`json.dumps(state, allow_nan=False)` 必须通过，且含 `rng_state`；
- `test_fitness_result_from_dict_roundtrip_and_validation`：往返相等，缺字段 / 类型错 / NaN 报错；
- `test_corrupt_or_incomplete_checkpoint_raises`：坏 JSON、只有版本号；
- `test_unsupported_schema_version_raises`：版本 99；
- `test_history_generation_mismatch_strict_and_non_strict`：篡改代际后 strict 抛错、非 strict 可续并留痕。

运行：

```powershell
python -m pytest -q evolution/test_v393_checkpoint.py
# 7 passed
```

同轮回归：`tests/ai_team` 614 passed；`evolution/test_evolution_history.py` + `test_alpha_evolution_history_integration.py` + 新增用例共 57 passed。

## 5. 使用示例

```python
from evolution.alpha_evolution import AlphaEvolutionEngine

engine = AlphaEvolutionEngine.from_checkpoint("experiments/runs/alpha.json")
engine.run(max_generations=5)
engine.save_checkpoint("experiments/runs/alpha.json")
```

## 6. 已知限制

- 单进程内可复现；**跨进程并发写同一 JSONL 历史仍无文件锁**（属 P3）。
- checkpoint 只保存进化状态，不含行情/因子原始数据；恢复后重跑评估仍需要数据可用。
- `restore_state` 要求 `experiment_name` 与目标引擎配置一致，跨实验复用需新建引擎。
