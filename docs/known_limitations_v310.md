# V3.10 已知限制（发布前如实披露）

本文件只记录**已经实测确认**的限制，以及本机无法验证的部分；不写推测。

## 1. 三个 AI 席位的 API 可达性

| 席位 | 协议 | 实测结果 | 处理方式 |
|---|---|---|---|
| ChatGPT | OpenAI `/chat/completions` | 直连 `api.openai.com` 报 `WinError 10060`，必须走代理；API 返回 429 `insufficient_quota` / `credit_balance_exhausted`（账户余额为 0） | 代码路径已跑通到「发请求 → 收 429」，真实出报告改走人工导入 |
| Grok | OpenAI 兼容（`api.x.ai`） | 免费版未拿到 `xai-` 前缀 key，提交的 key 被 xAI 判 `Incorrect API key provided` | 同上，人工导入 |
| Hark | 需自建 OpenAI 兼容网关 | Hark 没有公开文档化的模型 API，`HARK_API_KEY` / `HARK_BASE_URL` / `HARK_MODEL` 三项不齐时该席位记 `skipped` | 人工导入，或自建网关后补齐三项 |

因此：**“三席全绿”的完整自动验收尚未在本机完成**；已完成的真实验收是「两席人工报告导入 + 校验 + 落盘」，见 `docs/release_v310.md` 7.2、7.10。

## 2. 环境受限的测试用例（已在 Linux 云主机验证通过）

本机（Windows）无法执行的 5 个用例，已在云主机 Linux + 干净 venv（Python 3.12、chromadb 1.5.9、torch 2.15.0+cpu、xgboost、scikit-learn）跑通：**5 passed**。

| 用例 | 本机（Windows） | 云主机（Linux） |
|---|---|---|
| `tests/test_v11.py::test_chromadb_vector_store` | 未执行 | passed |
| `tests/test_v09.py::TestMemory::test_memory_save_search` | 未执行 | passed |
| `tests/test_v21.py::TestVectorMemory::test_save_and_search` | 原代码 import 不存在的 `memory.vector_memory`，任何平台都无法收集 | passed（已改为调用 `brain.memory.save_memory/search_memory`） |
| `tests/test_v27.py::TestMarketTransformer::test_forward_shape` | torch DLL 全 1 字节，`import torch` 报 `WinError 126 shm.dll` | passed |
| `tests/test_v27.py::TestXGBoostAlpha::test_train_predict` | 受同一 torch 问题影响 | passed |

本机 Windows 的限制仍然存在：torch CPU wheel 的 `c10.dll` / `cpuinfo.lib` 等为 1 字节，`import onnxruntime` 会原生崩溃（退出码 `-1073741819`），所以整套 `pytest` 不能在单进程里全仓跑；`tests/ai_team` 用 `--import-mode=importlib` 单独跑是安全的。

## 3. 超时语义

- `RetryPolicy.timeout_mode="thread"`（默认）超时会抛 `AgentTimeoutError`，但**卡住的线程无法强杀**，只是被放弃；
- 需要硬终止时必须显式传 `timeout_mode="process"`，代价是被调用的 callable 必须可 pickle（`_submit_one` 已改为可跨进程的 `_ReportCollectorCall`）。

## 4. 费用与速率

- `generate_reports(call_budget=..., token_budget=...)` 只是**本地预检**：超预算的席位不发请求，估算口径是 `prompt_chars // 4`，不是 provider 的真实计费 token；
- 429 退避尊重 `Retry-After`，但单次等待上限 `max_retry_wait=60s`，超过就放弃该席位而不是无限等待。

## 5. 未纳入本轮

- AkShare 实时行情接入（兼容层已修，但未做实时数据对接）；
- 发布 tag 与 PyPI 打包（当前只有 `ai_team.__version__ = "3.10.0"`，未打 git tag）。

## 6. Colab 验收席位（experimental，不计票）

- 2026-11-18 用 Colab 免费 T4 + Qwen2.5-1.5B 真机跑通了 `--live --providers-file`：
  真实 HTTP、真实推理、报告落盘、降级产物齐全，退出码 0。
- 该席位的定位是**链路验收工具**，不参与研究结论：1.5B 写出的报告会编造财务数据，
  且常常给不出来源，按既定规则一律 `seats_unsourced`，不计票。
- 它证明的是「代码通」，不是「结论对」。三席全绿的完整自动验收仍未完成：
  ChatGPT 余额为 0、Grok 免费版无 `xai-` key、Hark 无公开模型 API。
- 会话与地址都是临时的：Colab 会话关闭即失效，隧道地址每次重启都变，
  搭建步骤见 `docs/colab_endpoint.md`。
