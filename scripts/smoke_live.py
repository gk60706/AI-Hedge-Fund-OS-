from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_team.research_pipeline import V310ResearchPipeline
from ai_team.report_collector import ReportFormat
from ai_team.cross_validator import CrossValidator


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
        description="Import manual reports and validate an existing task"
    )
    parser.add_argument("--task-id", required=True, help="Existing task ID")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    imported, failures = [], {}
    pipeline = V310ResearchPipeline(min_reports=2, max_rounds=1)

    for agent_id, file_path in zip(args.import_report or [], args.file or []):
        try:
            content = Path(file_path).read_text(encoding="utf-8-sig")
            pipeline.report_collector.collect_report(
                task_id=args.task_id,
                agent_id=agent_id,
                content=content,
                title=f"Manual research: {agent_id}",
                report_format=ReportFormat.MARKDOWN,
                source="manual",
                allow_incomplete=True,
            )
            imported.append({"agent_id": agent_id, "status": "success"})
        except Exception as exc:
            failures[agent_id] = str(exc)
            imported.append({"agent_id": agent_id, "status": "failed"})

    validation = {"status": None, "validation_id": None, "seats": []}
    try:
        result = CrossValidator(
            task_manager=pipeline.task_manager,
            report_collector=pipeline.report_collector,
        ).validate_task(args.task_id)
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
        }
    except Exception as exc:
        failures["validation"] = str(exc)
        validation["status"] = "failed"

    records = pipeline.report_collector.list_reports(
        task_id=args.task_id
    )
    summary = {
        "task_id": args.task_id,
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
