# AI Hedge Fund OS V3.10 Desktop

Windows 桌面客户端。

## 1. 功能

- FastAPI 本地服务
- 中文 HTML/CSS/JavaScript 单页界面
- AI Provider 配置查看
- 多 AI 实时研究任务
- 后台线程执行研究
- 任务状态轮询
- 实时日志展示
- 研究结果 JSON 展示
- reports / research 文件浏览
- Markdown / JSON 文件预览
- Windows PyInstaller onedir 打包

## 2. 环境要求

- Windows 10 / 11 64-bit
- Python 3.11+
- 项目 V3.10 完整源码

运行时依赖：

- Python 标准库
- fastapi
- uvicorn
- PyYAML
- ai_team

不使用 pandas、numpy、torch、chromadb、
akshare、sklearn、matplotlib。

## 3. 项目结构

```text
AI-Hedge-Fund-OS/
│
├── ai_team/
│
├── configs/
│   ├── ai_providers.yaml
│   └── ai_providers.colab.yaml
│
├── reports/
├── research/
│
├── desktop/
│   ├── app.py
│   ├── ui.html
│   ├── launcher.py
│   ├── app.spec
│   └── README.md
│
├── .env
└── requirements.txt