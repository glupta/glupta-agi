"""Bounded Pydantic Evals loop for the frozen Crawl workload."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from .brief import build_user_prompt
from .contracts import EvidenceBrief
from .effects import initialize
from .settings import PINNED_CODEX_MODEL, Settings
from .workflow import _run_codex


@dataclass(frozen=True)
class EvalInput:
    question: str
    sources: list[dict[str, str]]


@dataclass(frozen=True)
class EvalExpected:
    required_points: list[str]
    required_uncertainties: list[str]
    forbidden_points: list[str]


def _contains(text: str, phrase: str) -> bool:
    return phrase.casefold() in text.casefold()


def _contains_forbidden(text: str, phrase: str, required_points: list[str]) -> bool:
    """Ignore only an exact required phrase that contains the forbidden phrase."""
    folded = text.casefold()
    phrase_folded = phrase.casefold()
    for required in required_points:
        if phrase_folded in required.casefold():
            folded = folded.replace(required.casefold(), "")
    return phrase_folded in folded


class GroundedBriefEvaluator(Evaluator[EvalInput, EvidenceBrief, EvalExpected]):
    """Score only deterministic properties declared by the frozen cases."""

    def evaluate(
        self, ctx: EvaluatorContext[EvalInput, EvidenceBrief, EvalExpected]
    ) -> dict[str, EvaluationReason]:
        expected = ctx.metadata
        if expected is None:
            raise ValueError("eval case is missing expected metadata")
        output = ctx.output
        response_text = "\n".join(
            [output.answer, *output.uncertainties, *output.next_decisions]
        )
        uncertainty_text = "\n".join(output.uncertainties)
        required = [
            point for point in expected.required_points if not _contains(response_text, point)
        ]
        uncertainties = [
            point
            for point in expected.required_uncertainties
            if not _contains(uncertainty_text, point)
        ]
        forbidden = [
            point
            for point in expected.forbidden_points
            if _contains_forbidden(response_text, point, expected.required_points)
        ]
        selected = {source["path"]: source["content"].splitlines() for source in ctx.inputs.sources}
        citations_valid = all(
            citation.path in selected
            and citation.line_start <= citation.line_end <= len(selected[citation.path])
            and citation.quote
            == "\n".join(selected[citation.path][citation.line_start - 1 : citation.line_end])
            for citation in output.citations
        )
        citations_present = not expected.required_points or bool(output.citations)
        return {
            "required_points": EvaluationReason(not required, _reason("missing", required)),
            "required_uncertainties": EvaluationReason(
                not uncertainties, _reason("missing", uncertainties)
            ),
            "forbidden_points": EvaluationReason(not forbidden, _reason("present", forbidden)),
            "citations_valid": EvaluationReason(citations_valid, None),
            "citations_present": EvaluationReason(citations_present, None),
        }


def _reason(label: str, phrases: list[str]) -> str | None:
    return f"{label}: {', '.join(phrases)}" if phrases else None


def load_dataset(
    path: Path, *, case_names: set[str] | None = None, limit: int | None = None
) -> Dataset[EvalInput, EvidenceBrief, EvalExpected]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[Case[EvalInput, EvidenceBrief, EvalExpected]] = []
    for item in raw["cases"]:
        if case_names and item["id"] not in case_names:
            continue
        sources = [{"path": name, "content": content} for name, content in item["files"].items()]
        cases.append(
            Case(
                name=item["id"],
                inputs=EvalInput(question=item["question"], sources=sources),
                metadata=EvalExpected(
                    required_points=item["required_points"],
                    required_uncertainties=item["required_uncertainties"],
                    forbidden_points=item["forbidden_points"],
                ),
            )
        )
        if limit is not None and len(cases) >= limit:
            break
    if case_names and {case.name for case in cases} != case_names:
        missing = sorted(case_names - {case.name for case in cases})
        raise ValueError(f"unknown eval case: {', '.join(missing)}")
    if not cases:
        raise ValueError("no eval cases selected")
    return Dataset(name="evidence_brief_v1", cases=cases, evaluators=[GroundedBriefEvaluator()])


def run_eval(dataset: Dataset[EvalInput, EvidenceBrief, EvalExpected]) -> Any:
    settings = Settings.from_environment()
    initialize(settings.dbos_system_database_url())

    def generate(item: EvalInput) -> EvidenceBrief:
        return _run_codex(
            build_user_prompt(item.question, item.sources),
            item.sources,
            str(settings.codex_home),
            PINNED_CODEX_MODEL,
            f"crawl-eval-{uuid.uuid4().hex}",
            hashlib.sha256(
                json.dumps(
                    {"question": item.question, "sources": item.sources},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        )

    return dataset.evaluate_sync(
        generate,
        name=f"crawl-{PINNED_CODEX_MODEL}",
        task_name="evidence_brief_v1",
        max_concurrency=1,
        progress=True,
        metadata={"model": PINNED_CODEX_MODEL},
    )


def build_receipt(report: Any, dataset_path: Path) -> dict[str, Any]:
    cases = []
    for case in report.cases:
        assertions = {name: result.value for name, result in case.assertions.items()}
        cases.append(
            {
                "id": case.name,
                "duration_seconds": round(case.task_duration, 3),
                "passed": all(assertions.values()) and not case.evaluator_failures,
                "assertions": assertions,
                "output": case.output.model_dump(mode="json"),
                "reasons": {
                    name: result.reason
                    for name, result in case.assertions.items()
                    if result.reason
                },
            }
        )
    failures = [{"id": item.name, "error": item.error_message} for item in report.failures]
    return {
        "schema": "CrawlEvalReceiptV1",
        "created_at": datetime.now(UTC).isoformat(),
        "model": PINNED_CODEX_MODEL,
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "passed": not failures and all(item["passed"] for item in cases),
        "case_count": len(cases) + len(failures),
        "cases": cases,
        "failures": failures,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evals/evidence_brief_v1.json"))
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    dataset = load_dataset(args.dataset, case_names=set(args.cases or []), limit=args.limit)
    report = run_eval(dataset)
    print(report.render(include_reasons=True))
    receipt = build_receipt(report, args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if receipt["passed"] else 1)


if __name__ == "__main__":
    main()
