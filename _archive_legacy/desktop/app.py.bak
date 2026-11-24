from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    UI_FILE = Path(sys._MEIPASS) / "desktop" / "ui.html"
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    UI_FILE = Path(__file__).resolve().parent / "ui.html"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ai_team
from ai_team.providers import (
    load_providers,
    build_custom_registry,
    describe_providers,
)
from ai_team.research_pipeline import V310ResearchPipeline


app = FastAPI(
    title="AI Hedge Fund OS V3.10",
    version="3.10",
)

jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )
        )
    except Exception:
        return str(value)


def resolve_config_path(value: str) -> Path:
    path = Path(value)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    try:
        path = path.resolve()
        path.relative_to(PROJECT_ROOT.resolve())
    except (ValueError, OSError):
        raise HTTPException(
            status_code=400,
            detail="配置文件路径越界",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="配置文件不存在",
        )

    return path


def append_log(job_id: str, message: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is not None:
            job["log"].append(str(message))
            job["log"] = job["log"][-200:]


def update_job(job_id: str, **kwargs):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


class JobLogHandler(logging.Handler):
    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def emit(self, record):
        try:
            append_log(
                self.job_id,
                self.format(record),
            )
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
def index():
    if not UI_FILE.is_file():
        raise HTTPException(
            status_code=500,
            detail=f"ui.html 不存在: {UI_FILE}",
        )

    return UI_FILE.read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": getattr(ai_team, "__version__", "unknown"),
    }


@app.get("/api/providers")
def providers(file: str = "configs/ai_providers.yaml"):
    path = resolve_config_path(file)

    try:
        loaded_providers = load_providers(path)
        registry = build_custom_registry(
            path,
            timeout=10,
        )

        rows = describe_providers(
            registry,
            loaded_providers,
        )

        result = []

        for row in rows:
            item = {
                "provider_id": row.get("provider_id"),
                "display_name": row.get("display_name"),
                "base_url": row.get("base_url"),
                "model": row.get("model"),
                "status": row.get("status"),
            }

            if "tags" in row:
                item["tags"] = row["tags"]

            result.append(item)

        return result

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Provider 加载失败: {type(exc).__name__}: {exc}",
        )


class ResearchRequest(BaseModel):
    symbol: str = Field(
        default="300394.SZ",
        min_length=1,
        max_length=32,
    )
    as_of: str
    providers_file: str = "configs/ai_providers.yaml"
    allow_missing_agents: bool = True
    call_budget: int = Field(
        default=1,
        ge=1,
        le=100,
    )
    adapter_timeout: int = Field(
        default=300,
        ge=1,
        le=3600,
    )


def execute_research(
    job_id: str,
    request: ResearchRequest,
):
    handler = JobLogHandler(job_id)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        )
    )

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    try:
        update_job(
            job_id,
            status="running",
            started_at=now_iso(),
        )

        append_log(job_id, "初始化 V3.10 Research Pipeline")
        append_log(job_id, f"研究标的: {request.symbol}")
        append_log(job_id, f"截止日期: {request.as_of}")

        config_path = resolve_config_path(
            request.providers_file
        )

        append_log(job_id, "加载 Provider 配置")

        registry = build_custom_registry(
            config_path,
            timeout=request.adapter_timeout,
        )

        reports_dir = (
            PROJECT_ROOT
            / "reports"
            / f"{request.symbol}_{request.as_of}"
        )

        reports_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        append_log(job_id, f"报告目录: {reports_dir}")
        append_log(job_id, "创建研究 Pipeline")

        pipeline = V310ResearchPipeline(
            project_root=PROJECT_ROOT,
        )

        append_log(job_id, "开始执行多 AI 研究")

        result = pipeline.run_live(
            symbol=request.symbol,
            registry=registry,
            as_of_date=request.as_of,
            reports_dir=reports_dir,
            allow_missing_agents=request.allow_missing_agents,
            call_budget=request.call_budget,
        )

        result_data = safe_json(result)

        if isinstance(result_data, dict):
            stage = result_data.get("stage", "unknown")
            reports_collected = result_data.get(
                "reports_collected",
                0,
            )
        else:
            stage = getattr(result, "stage", "completed")
            reports_collected = getattr(
                result,
                "reports_collected",
                0,
            )

        append_log(job_id, "研究执行完成")
        append_log(job_id, f"stage: {stage}")
        append_log(
            job_id,
            f"reports_collected: {reports_collected}",
        )

        update_job(
            job_id,
            status="done",
            finished_at=now_iso(),
            result=result_data,
            error=None,
        )

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

        append_log(job_id, "研究执行失败: " + error)
        append_log(job_id, traceback.format_exc())

        update_job(
            job_id,
            status="error",
            finished_at=now_iso(),
            error=error,
        )

    finally:
        root_logger.removeHandler(handler)
        handler.close()


@app.post("/api/research")
def start_research(request: ResearchRequest):
    if not request.symbol.strip():
        raise HTTPException(
            status_code=400,
            detail="股票代码不能为空",
        )

    try:
        datetime.strptime(
            request.as_of,
            "%Y-%m-%d",
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="截止日期必须使用 YYYY-MM-DD 格式",
        )

    resolve_config_path(request.providers_file)

    job_id = uuid.uuid4().hex

    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
            "log": ["任务已进入队列"],
        }

    thread = threading.Thread(
        target=execute_research,
        args=(job_id, request),
        name=f"research-{job_id[:8]}",
        daemon=True,
    )

    thread.start()

    return {
        "job_id": job_id,
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="任务不存在",
            )

        return safe_json(job)


def collect_files():
    results = []

    for folder_name in ("reports", "research"):
        folder = PROJECT_ROOT / folder_name

        if not folder.is_dir():
            continue

        for path in folder.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix.lower() not in (
                ".json",
                ".md",
            ):
                continue

            try:
                stat = path.stat()

                results.append({
                    "path": path.relative_to(
                        PROJECT_ROOT
                    ).as_posix(),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })

            except OSError:
                continue

    results.sort(
        key=lambda item: item["mtime"],
        reverse=True,
    )

    return results[:30]


@app.get("/api/files")
def list_files():
    return {
        "files": collect_files(),
    }


@app.get("/api/files/{file_path:path}")
def read_file(file_path: str):
    if not file_path:
        raise HTTPException(
            status_code=400,
            detail="文件路径不能为空",
        )

    requested = Path(file_path)

    if requested.is_absolute():
        raise HTTPException(
            status_code=400,
            detail="禁止绝对路径",
        )

    try:
        target = (
            PROJECT_ROOT / requested
        ).resolve()

        target.relative_to(
            PROJECT_ROOT.resolve()
        )

    except (ValueError, OSError):
        raise HTTPException(
            status_code=403,
            detail="文件路径越界",
        )

    if target.suffix.lower() not in (
        ".json",
        ".md",
    ):
        raise HTTPException(
            status_code=403,
            detail="不支持的文件类型",
        )

    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail="文件不存在",
        )

    try:
        content = target.read_text(
            encoding="utf-8-sig",
        )

        return {
            "path": target.relative_to(
                PROJECT_ROOT
            ).as_posix(),
            "content": content,
        }

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=415,
            detail="文件不是有效 UTF-8 文本",
        )

    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
    )