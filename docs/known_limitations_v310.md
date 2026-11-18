# V3.10 已知限制（发布前如实披露）

本文件只记录**已经实测确认**的限制，以及本机无法验证的部分；不写推测。

## 1. 三个 AI 席位的 API 可达性

| 席位 | 协议 | 实测结果 | 处理方式 |
|---|---|---|---|
| ChatGPT | OpenAI `/chat/completions` | 直连 `api.openai.com` 报 `WinError 10060`，必须走代理；API 返回 429 `insufficient_quota` / `credit_balance_exhausted`（账户余额为 0） | 代码路径已跑通到「发请求 → 收 429」，真实出报告改走人工导入 |
| Grok | OpenAI 兼容（`api.x.ai`） | 免费版未拿到 `xai-` 前缀 key，提交的 key 被 xAI 判 `Incorrect API key provided` | 同上，人工导入 |
| Hark | 需自建 OpenAI 兼容网关 | Hark 没有公开文档化的模型 API，`HARK_API_KEY` / `HARK_BASE_URL` / `HARK_MODEL` 三项不齐时该席位记 `skipped` | 人工导入，或自建网关后补齐三项 |

因此：**“三席全绿”的完整自动验收尚未在本机完成**；已完成的真实验收是「两席人工报告导入 + 校验 + 落盘」，见 `docs/release_v310.md` 7.2、7.10。

## 2. 本机环境受限的测试用例

- chromadb 向量库 3 例：`tests/test_v09.py::TestMemory::test_memory_save_search`、`tests/test_v11.py::test_chromadb_vector_store`、`tests/test_v21.py::TestVectorMemory::test_save_and_search`。本机 chromadb 依赖的原生运行时不可用，**未在本机执行**；`tests/ai_team` 全量不受影响。
- torch 相关 2 个形状用例：CPU wheel 安装后 `torch\lib` 下 `c10.dll` / `c10.lib` / `cpuinfo.lib` / `libshm` / `mimalloc-2.5` 均为 1 字节，`import torch` 报 `OSError: [WinError 126] shm.dll`；已卸载 torch，**未在本机执行**。
- `import onnxruntime` 在本机会直接触发原生崩溃（退出码 `-1073741819`），因此整套 `pytest` 不能在单进程里全仓跑；`tests/ai_team` 用 `--import-mode=importlib` 单独跑是安全的。

以上三项属于**环境限制，不是代码回归**；如需要在 CI 或 Linux 上验证，应在干净虚拟环境里单独跑这三组用例。

## 3. 超时语义

- `RetryPolicy.timeout_mode="thread"`（默认）超时会抛 `AgentTimeoutError`，但**卡住的线程无法强杀**，只是被放弃；
- 需要硬终止时必须显式传 `timeout_mode="process"`，代价是被调用的 callable 必须可 pickle（`_submit_one` 已改为可跨进程的 `_ReportCollectorCall`）。

## 4. 费用与速率

- `generate_reports(call_budget=..., token_budget=...)` 只是**本地预检**：超预算的席位不发请求，估算口径是 `prompt_chars // 4`，不是 provider 的真实计费 token；
- 429 退避尊重 `Retry-After`，但单次等待上限 `max_retry_wait=60s`，超过就放弃该席位而不是无限等待。

## 5. 未纳入本轮

- AkShare 实时行情接入（兼容层已修，但未做实时数据对接）；
- 发布 tag 与 PyPI 打包（当前只有 `ai_team.__version__ = "3.10.0"`，未打 git tag）。
