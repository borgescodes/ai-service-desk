import json
import shutil
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from ai_service_desk.engine.index import atomic_json
from ai_service_desk.engine.playbook import (
    build_playbook_catalog,
    load_playbook_catalog,
    load_playbooks,
)
from ai_service_desk.engine.playbook_resolution import (
    PlaybookEngine,
    action_proposal_descriptor,
    format_playbook_result,
)

CASE_FIELDS = {
    "case_name",
    "mode",
    "knowledge_id",
    "expected_status",
    "expected_reason",
    "expected_playbook_id",
    "mutation",
}
ALLOWED_MODES = {"RESOLVE", "BUILD_ERROR", "LOAD_ERROR", "ACTION_CONTRACT"}
ALLOWED_MUTATIONS = {"", "APPROVED_CONFLICT", "INELIGIBLE_REFERENCE", "CATALOG_TAMPER"}


def load_playbook_cases(path: str | Path) -> list[dict]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ValueError("Arquivo de casos de playbook nao encontrado.")
    rows: list[dict] = []
    seen: set[str] = set()
    try:
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON invalido na linha {line_number}.") from exc
                if not isinstance(raw, dict) or set(raw) != CASE_FIELDS:
                    raise ValueError("Campos invalidos no caso de playbook.")
                name = raw["case_name"]
                if not isinstance(name, str) or not name.strip() or name in seen:
                    raise ValueError("case_name invalido ou duplicado.")
                mode = raw["mode"]
                mutation = raw["mutation"]
                if mode not in ALLOWED_MODES:
                    raise ValueError("mode invalido no caso de playbook.")
                if mutation not in ALLOWED_MUTATIONS:
                    raise ValueError("mutation invalida no caso de playbook.")
                for field in (
                    "knowledge_id",
                    "expected_status",
                    "expected_reason",
                    "expected_playbook_id",
                ):
                    if not isinstance(raw[field], str):
                        raise ValueError(f"{field} deve ser texto.")
                if not raw["knowledge_id"].strip():
                    raise ValueError("knowledge_id invalido no caso de playbook.")
                seen.add(name)
                rows.append(dict(raw))
    except UnicodeDecodeError as exc:
        raise ValueError("Casos de playbook devem ser JSONL UTF-8 valido.") from exc
    if len(rows) != 10:
        raise ValueError("Smoke da Fase 6 exige exatamente 10 casos sinteticos.")
    return rows


def _write_source(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _case_summary(case: dict, actual_status: str, actual_reason: str, actual_playbook_id) -> dict:
    passed = (
        actual_status == case["expected_status"]
        and actual_reason == case["expected_reason"]
        and (actual_playbook_id or "") == case["expected_playbook_id"]
    )
    return {
        "case_name": case["case_name"],
        "expected_status": case["expected_status"],
        "actual_status": actual_status,
        "expected_reason": case["expected_reason"],
        "actual_reason": actual_reason,
        "expected_playbook_id": case["expected_playbook_id"] or None,
        "actual_playbook_id": actual_playbook_id,
        "passed": bool(passed),
    }


def _result_values(result: dict) -> tuple[str, str, str | None]:
    playbook = result.get("playbook") or {}
    return result.get("status", ""), result.get("reason", ""), playbook.get("playbook_id")


def run_playbook_smoke(
    knowledge_index: str | Path,
    playbook_source: str | Path,
    cases_path: str | Path,
    work_directory: str | Path,
    report_path: str | Path,
) -> dict:
    report = {
        "schema_version": 1,
        "phase": 6,
        "domain": "APPROVED_PLAYBOOK",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "ok": False,
        "cases": [],
        "privacy": {
            "raw_text_included": False,
            "approved_content_included": False,
            "capability_included": False,
            "corporate_data_included": False,
        },
    }
    try:
        cases = load_playbook_cases(cases_path)
        work = Path(work_directory)
        work.mkdir(parents=True, exist_ok=True)
        base_catalog = work / "base-catalog"
        if base_catalog.exists():
            shutil.rmtree(base_catalog)
        build_playbook_catalog(playbook_source, knowledge_index, base_catalog)
        engine = PlaybookEngine(base_catalog, knowledge_index)
        source_rows = load_playbooks(playbook_source)

        for case in cases:
            actual_status = "EXECUTION_ERROR"
            actual_reason = "ValueError"
            actual_playbook_id = None
            try:
                mode = case["mode"]
                if mode == "RESOLVE":
                    result = engine.resolve_knowledge_id(case["knowledge_id"])
                    actual_status, actual_reason, actual_playbook_id = _result_values(result)
                elif mode == "ACTION_CONTRACT":
                    result = engine.resolve_knowledge_id(case["knowledge_id"])
                    actual_status, actual_reason, actual_playbook_id = _result_values(result)
                    playbook = result.get("playbook") or {}
                    action = next(
                        step
                        for step in playbook.get("steps", [])
                        if step.get("type") == "ACTION_PROPOSAL"
                    )
                    descriptor = action_proposal_descriptor(case["knowledge_id"], playbook, action)
                    rendered = format_playbook_result(result)
                    if descriptor.get("capability") != action.get("capability"):
                        raise ValueError("Descriptor Phase 7 divergente da capability estruturada.")
                    if action.get("capability") in rendered:
                        raise ValueError("Formatter de usuario expos capability interna.")
                elif mode == "BUILD_ERROR":
                    mutated = deepcopy(source_rows)
                    if case["mutation"] == "APPROVED_CONFLICT":
                        base = next(
                            row
                            for row in mutated
                            if row["status"] == "APPROVED"
                            and case["knowledge_id"] in row["knowledge_ids"]
                        )
                        duplicate = deepcopy(base)
                        duplicate["playbook_id"] = "PB-SYN-CONFLICT-999"
                        mutated.append(duplicate)
                    elif case["mutation"] == "INELIGIBLE_REFERENCE":
                        target = next(row for row in mutated if row["status"] == "APPROVED")
                        target["knowledge_ids"] = [case["knowledge_id"]]
                    else:
                        raise ValueError("Mutation BUILD_ERROR invalida.")
                    temp_source = work / f"{case['case_name']}.jsonl"
                    temp_catalog = work / f"{case['case_name']}-catalog"
                    _write_source(temp_source, mutated)
                    try:
                        build_playbook_catalog(temp_source, knowledge_index, temp_catalog)
                    except ValueError as exc:
                        actual_status = "BUILD_ERROR"
                        actual_reason = type(exc).__name__
                    else:
                        actual_status = "UNEXPECTED_SUCCESS"
                        actual_reason = ""
                elif mode == "LOAD_ERROR":
                    if case["mutation"] != "CATALOG_TAMPER":
                        raise ValueError("Mutation LOAD_ERROR invalida.")
                    temp_catalog = work / f"{case['case_name']}-catalog"
                    if temp_catalog.exists():
                        shutil.rmtree(temp_catalog)
                    build_playbook_catalog(playbook_source, knowledge_index, temp_catalog)
                    catalog_path = temp_catalog / "playbook-catalog.json"
                    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                    first_id = sorted(catalog["playbooks"])[0]
                    catalog["playbooks"][first_id]["title"] = "Titulo sintetico adulterado"
                    atomic_json(catalog_path, catalog)
                    try:
                        load_playbook_catalog(temp_catalog, knowledge_index)
                    except ValueError as exc:
                        actual_status = "LOAD_ERROR"
                        actual_reason = type(exc).__name__
                    else:
                        actual_status = "UNEXPECTED_SUCCESS"
                        actual_reason = ""
                else:
                    raise ValueError("Mode de smoke nao suportado.")
            except (ValueError, RuntimeError, OSError, KeyError, StopIteration, AssertionError) as exc:
                actual_status = "EXECUTION_ERROR"
                actual_reason = type(exc).__name__
                actual_playbook_id = None
            report["cases"].append(
                _case_summary(case, actual_status, actual_reason, actual_playbook_id)
            )
        report["ok"] = len(report["cases"]) == 10 and all(
            row["passed"] for row in report["cases"]
        )
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        report["error"] = type(exc).__name__
    finally:
        atomic_json(Path(report_path), report)
    return report
