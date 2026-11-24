from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_team.research_pipeline import DEFAULT_PARTICIPANTS, V310ResearchPipeline
from ai_team.report_collector import InvalidReportError, ReportFormat
from ai_team.source_extraction import extract_sources_from_content


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import manual reports and validate a task"
    )
    parser.add_argument("--task-id")
    parser.add_argument(
        "--task", choices=("existing", "new"), default="existing",
        help="Validate an existing task or create a new one",
    )
    parser.add_argument("--symbol", help="Symbol for --task new")
    parser.add_argument("--as-of", default="")
    parser.add_argument("--max-agents", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--import-report", action="append",
        choices=("chatgpt", "grok", "hark"),
        help="Report agent ID; repeatable",
    )
    parser.add_argument("--file", action="append", help="Report file")
    parser.add_argument(
        "--artifact", default="artifacts/smoke/run.json",
        help="JSON artifact output path",
    )
    args = parser.parse_args()

    if args.task == "new" and not args.symbol:
        parser.error("--task new requires --symbol")
    if args.task == "existing" and not args.task_id:
        parser.error("--task existing requires --task-id")
    if args.max_agents < 1:
        parser.error("--max-agents must be >= 1")

    return args


def main() -> int:
    args = parse_args()
    imported, failures = [], {}
    pipeline = V310ResearchPipeline(min_reports=2, max_rounds=1)

    participants = (
        DEFAULT_PARTICIPANTS[: args.max_agents]
        if args.task == "new"
        else []
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "task_id": args.task_id or None,
                    "task": args.task,
                    "participants": list(participants),
                    "file_count": len(args.file or []),
                    "dry_run": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.task == "new":
        title = f"{args.symbol} {args.as_of}" if args.as_of else None
        task_id = pipeline.start_task(
            args.symbol,
            title=title,
            participants=participants,
        )
    else:
        task_id = args.task_id

    if len(args.import_report or []) != len(args.file or []):
        error = "--import-report and --file counts must match"
        failures["args"] = error
        print(
            json.dumps({"task_id": task_id}, ensure_ascii=False),
            file=sys.stderr,
        )
        print(error, file=sys.stderr)
        return 2

    for agent_id, file_path in zip(args.import_report or [], args.file or []):
        try:
            content = Path(file_path).read_text(encoding="utf-8-sig")
            sources = extract_sources_from_content(content)
            try:
                pipeline.report_collector.collect_report(
                    task_id=task_id,
                    agent_id=agent_id,
                    content=content,
                    title=f"Manual research: {agent_id}",
                    report_format=ReportFormat.MARKDOWN,
                    source="manual",
                    allow_incomplete=True,
                    sources=sources,
                )
                imported.append(
                    {
                        "agent_id": agent_id,
                        "status": "success",
                        "sources_detected": bool(sources),
                    }
                )
            except InvalidReportError:
                pipeline.report_collector.collect_report(
                    task_id=task_id,
                    agent_id=agent_id,
                    content=content,
                    title=f"Manual research: {agent_id}",
                    report_format=ReportFormat.MARKDOWN,
                    source="manual",
                    allow_incomplete=True,
                    sources=None,
                )
                imported.append(
                    {
                        "agent_id": agent_id,
                        "status": "success",
                        "sources_detected": False,
                        "sources_invalid": True,
                    }
                )
        except Exception as exc:
            failures[agent_id] = str(exc)
            imported.append(
                {
                    "agent_id": agent_id,
                    "status": "failed",
                    "sources_detected": False,
                }
            )

    validation = {"status": None, "validation_id": None, "seats": []}
    try:
        pipeline.resume(task_id)
        result = pipeline.validate()
        validation = {
            "status": result.status,
            "validation_id": result.validation_id,
            "seats": [
                {
                    "agent_id": a.agent_id,
                    "quality_score": a.quality_score,
                    "evidence_score": a.evidence_score,
                    "claims": len(a.claims),
                    "warnings": len(a.warnings),
                }
                for a in result.agent_analyses
            ],
            "warnings": getattr(result, "warnings", []) or [],
            "metadata": getattr(result, "metadata", {}) or {},
        }
    except Exception as exc:
        failures["validation"] = str(exc)
        validation["status"] = "failed"

    records = pipeline.report_collector.list_reports(
        task_id=task_id
    )
    summary = {
        "task_id": task_id,
        "imported": imported,
        "failures": failures,
        "report_count": len(records),
        "validation": validation,
    }
    output = json.dumps(
        summary, ensure_ascii=False, indent=2, default=str
    )
    atomic_write(Path(args.artifact), output)
    print(output)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
