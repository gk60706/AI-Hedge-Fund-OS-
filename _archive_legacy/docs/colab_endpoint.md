# Colab 免费 GPU 当作「验收端点」

本文件记录一次**已实测跑通**的做法：把 Google Colab 免费版 Tesla T4 变成一个
OpenAI 兼容端点，用真实 HTTP、真实模型推理跑通
`research_pipeline --live --providers-file` 这条链路。

它的定位只有一个：**发布前的链路验收工具 + 试验场**，不是研究席位。

## 1. 能证明什么、不能证明什么

能证明：

- `configs/ai_providers.colab.yaml` → `build_custom_registry` → 真实 HTTP → 报告落盘 → 提交/降级 → 产物 JSON 全链路通；
- 429、超时、不完整报告、零报告这些分支在真实数据下是什么行为；
- `--providers-file` 这条 V3.10 新增代码确实可用。

不能证明：

- 研究质量。1.5B 量化模型写的研报会编造财务数据，且常常过不了来源契约，
  本项目一律按「无来源不计票」处理；
- 稳定性。免费会话有 12 小时上限，隧道地址每次重启都变。

## 2. Colab 侧

1. 打开 https://colab.research.google.com/ ，新建 notebook，`代码执行程序 → 更改运行时类型 → T4 GPU`。
2. 单格执行一段启动脚本：装 `fastapi uvicorn transformers accelerate`，
   下载 `cloudflared-linux-amd64`，起一个 OpenAI 兼容的 uvicorn 服务（`/v1/models`、
   `/v1/chat/completions`），再起一条 quick tunnel。
3. 从 `tunnel.log` 里取地址（`tail` 抓不到，用 `grep trycloudflare`）：

   ```text
   https://<随机词>-<随机词>-<随机词>.trycloudflare.com
   ```

注意：Colab 编辑器是 Monaco，`%%bash` 直接起后台进程会被 `Process is terminated.` 杀掉；
heredoc 多行脚本会被自动缩进打乱。稳妥做法是**把脚本 base64 成单行**再写入：

```python
!bash -c 'echo <B64_APP> | base64 -d > /content/app.py; echo <B64_LAUNCH> | base64 -d > /content/launch.sh; bash /content/launch.sh'
```

## 3. 本机侧

```powershell
$env:HARK_BASE_URL = "https://xxx.trycloudflare.com/v1"
$env:AIH_HARK_API_KEY = "colab-dummy"

python -m ai_team.providers check --file configs\ai_providers.colab.yaml
# -> OK hark Qwen/Qwen2.5-1.5B-Instruct

python -m ai_team.research_pipeline --symbol 300394.SZ `
  --reports-dir reports\colab_smoke --live `
  --providers-file configs\ai_providers.colab.yaml `
  --allow-missing-agents --call-budget 1 --adapter-timeout 300 --as-of 2026-11-18
```

`provider_id` 必须是 `hark`：`AGENT_ROLE_NAMES` 只认 chatgpt / grok / hark
三个席位，写别的 id 会在 `build_agent_prompt` 触发 `unknown agent_id`。
key 用任意字符串即可（服务端不校验），但**不要**写进 `.env` 提交。

## 4. 实测结果（2026-11-18）

| 项 | 值 |
|---|---|
| GPU | Tesla T4 / 15360MiB |
| 模型 | Qwen/Qwen2.5-1.5B-Instruct |
| 单次 673 字报告耗时 | 16.1s（`finish_reason=stop`） |
| provider 自检 | `OK hark` |
| 首次结果 | 报告被 `InvalidReportError: Incomplete report submission is not allowed.` 拒收，`validate()` 抛 `InsufficientReportsError`，退出码 1 |
| 修复后结果 | `stage=degraded_insufficient_reports`，`reports_collected=1`，`validation=not_performed`，退出码 0，落盘 `reports/degraded.json` |

首次那次失败是**真缺陷**，不是 Colab 的问题：提交阶段硬编码 `allow_incomplete=False`，
而 `allow_missing_agents=True` 又覆盖不到「零报告」情形。补丁见
`ai_team/research_pipeline.py` 的 `_submit_once` / `_degraded_result`，
回归测试见 `tests/ai_team/test_pipeline_degraded.py`。

## 5. 用完即弃

- 关闭 Colab 标签页 → 运行时释放，`/content` 清空，隧道失效；
- 下次使用要重跑启动格，**地址会变**，需要重新设 `HARK_BASE_URL`；
- 模型权重每次都要重新下载（约 3GB，几十秒到几分钟）。
- 不要用多个 Google 账号绕过配额；需要绑卡实名的平台不要碰。
