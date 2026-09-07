import argparse
import json
import sys
import time
from pathlib import Path

from ai_service_desk.engine.corpus import audit_corpus, ensure_external_path, write_safe_report
from ai_service_desk.engine.data import load_corpus, prepare_tiflux
from ai_service_desk.engine.demo_subset import build_demo_subset
from ai_service_desk.engine.index import atomic_json, build_index, import_legacy, load_index
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.real_smoke import run_real_smoke
from ai_service_desk.engine.retrieval import RetrievalEngine, format_result
from ai_service_desk.engine.smoke import run_validation

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_THRESHOLD = 0.65


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Service Desk: motor local de historicos, sem execucao de acoes."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--url", default=DEFAULT_URL)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--file", type=Path, required=True)

    audit = sub.add_parser("audit")
    audit.add_argument("--file", type=Path, required=True)
    audit.add_argument("--manifest", type=Path, required=True)
    audit.add_argument("--report", type=Path, required=True)

    demo_subset = sub.add_parser("demo-subset")
    demo_subset.add_argument("--file", type=Path, required=True)
    demo_subset.add_argument("--output", type=Path, required=True)
    demo_subset.add_argument("--report", type=Path, required=True)
    demo_subset.add_argument("--checkout", type=Path, required=True)
    demo_subset.add_argument("--per-group", type=int, default=40)

    real_smoke = sub.add_parser("real-smoke")
    real_smoke.add_argument("--file", type=Path, required=True)
    real_smoke.add_argument("--manifest", type=Path, required=True)
    real_smoke.add_argument("--index", type=Path, required=True)
    real_smoke.add_argument("--report", type=Path, required=True)
    real_smoke.add_argument("--checkout", type=Path, required=True)
    real_smoke.add_argument("--url", default=DEFAULT_URL)

    show_index = sub.add_parser("show-index")
    show_index.add_argument("--index", type=Path, required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--tickets", type=Path, required=True)
    prepare.add_argument("--appointments", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--scope", choices=["ti", "todos"], default="ti")

    index = sub.add_parser("index")
    index.add_argument("--file", type=Path, required=True)
    index.add_argument("--index", type=Path, required=True)
    index.add_argument("--batch-size", type=int, default=10)
    index.add_argument("--url", default=DEFAULT_URL)

    legacy = sub.add_parser("import-legacy")
    legacy.add_argument("--source", type=Path, required=True)
    legacy.add_argument("--index", type=Path, required=True)
    legacy.add_argument("--url", default=DEFAULT_URL)

    search = sub.add_parser("search")
    search.add_argument("--index", type=Path, required=True)
    search.add_argument("--query")
    search.add_argument("--show-history", action="store_true")
    search.add_argument("--context-json", type=Path)
    search.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    search.add_argument("--url", default=DEFAULT_URL)

    validate = sub.add_parser("validate")
    validate.add_argument("--file", type=Path, required=True)
    validate.add_argument("--index", type=Path, required=True)
    validate.add_argument("--report", type=Path, required=True)
    validate.add_argument("--legacy", type=Path)
    validate.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    validate.add_argument("--url", default=DEFAULT_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = None
    try:
        if args.command == "inspect":
            data = load_corpus(args.file)
            print(f"Registros: {len(data)}")
            print("Colunas: " + ", ".join(data.columns))
            print("Nenhum texto de atendimento foi exibido. Nenhuma chamada de IA foi feita.")
            return 0

        if args.command == "audit":
            report = audit_corpus(args.file, args.manifest)
            write_safe_report(args.report, report)
            summary = {
                key: report[key]
                for key in (
                    "rows",
                    "unique_ticket_ids",
                    "empty_ticket_ids",
                    "empty_search_texts",
                    "with_history",
                    "limited_texts",
                    "raw_sha256",
                    "canonical_sha256",
                    "manifest_match",
                )
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print("Auditoria por regras concluida. Nenhum conteudo de ticket foi exibido.")
            return 0

        if args.command == "demo-subset":
            source = ensure_external_path(args.file, args.checkout)
            output = ensure_external_path(args.output, args.checkout)
            report_path = ensure_external_path(args.report, args.checkout)
            if output.exists():
                raise ValueError("Subset de demo ja existe. Remova-o ou escolha outro --output.")
            data = load_corpus(source)
            subset, report = build_demo_subset(data, args.per_group)
            output.parent.mkdir(parents=True, exist_ok=True)
            subset.to_csv(output, sep=";", encoding="utf-8-sig", index=False)
            atomic_json(report_path, report)
            print(f"Subset de demo: {report['selected_rows']} registros")
            print(f"Registros por grupo: {report['per_group']}")
            print("Relatorio agregado local: " + str(report_path))
            return 0

        if args.command == "real-smoke":
            report = run_real_smoke(
                args.file,
                args.manifest,
                args.index,
                args.report,
                args.url,
                args.checkout,
            )
            prefix = "REAL CORPUS SMOKE OK" if report["ok"] else "REAL CORPUS SMOKE REQUER REVISAO"
            rows = report.get("corpus", {}).get("rows", report.get("index", {}).get("rows", 0))
            shape = report.get("index", {}).get("shape", [0, 0])
            print(prefix)
            print(f"Registros auditados: {rows}")
            print(f"Vetores validados: {shape[0]} x {shape[1]}")
            print(f"Casos sinteticos: {len(report.get('queries', []))}")
            print("Relatorio agregado local: " + str(args.report))
            return 0 if report["ok"] else 1

        if args.command == "show-index":
            _, _, state = load_index(args.index)
            safe = {
                key: state[key]
                for key in ("rows", "dimensions", "model", "model_digest", "complete", "recipe")
            }
            print(json.dumps(safe, ensure_ascii=False, indent=2))
            return 0

        if args.command == "prepare":
            if args.output.exists():
                raise ValueError("Arquivo de saida ja existe. Escolha outro --output.")
            data, report = prepare_tiflux(args.tickets, args.appointments, args.scope)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(args.output, sep=";", encoding="utf-8-sig", index=False)
            atomic_json(args.output.with_suffix(".report.json"), report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print("Corpus preparado em: " + str(args.output))
            return 0

        if args.command == "validate":
            report = run_validation(
                args.file,
                args.index,
                args.report,
                args.url,
                args.legacy,
                args.threshold,
            )
            print("VALIDACAO FUNCIONAL OK" if report["ok"] else "VALIDACAO REQUER REVISAO")
            print("Relatorio: " + str(args.report))
            return 0 if report["ok"] else 1

        if args.command == "search" and args.context_json and not args.query:
            raise ValueError("--context-json requer --query para evitar gravacao de conversas.")

        client = OllamaClient(args.url)
        if args.command == "doctor":
            print("Ollama: " + client.version())
            for model in ("qwen3.5:4b", "qwen3-embedding:0.6b"):
                info = client.model_info(model)
                print(model + " | digest " + info["digest"])
            print("Aplicacao configurada somente para loopback. Nenhum modelo foi baixado.")
            return 0

        embedder = LocalEmbedder(client)
        if args.command == "index":
            data = load_corpus(args.file)
            started = time.perf_counter()

            def progress(done: int, total: int) -> None:
                elapsed = time.perf_counter() - started
                print(
                    f"{done}/{total} registros salvos | {elapsed:.1f}s nesta execucao", flush=True
                )

            state = build_index(data, args.index, embedder, args.batch_size, progress)
            print(f"Indice pronto: ({state['rows']}, {state['dimensions']}) | {args.index}")
            return 0

        if args.command == "import-legacy":
            state = import_legacy(args.source, args.index, embedder)
            print(
                f"Importados {state['rows']} registros. "
                "Validacao por tres sentinelas, nao por todos os vetores."
            )
            return 0

        if args.command == "search":
            engine = RetrievalEngine(args.index, client, embedder, args.threshold)
            client.model_info("qwen3.5:4b")
            if args.query:
                result = engine.search(args.query)
                print(format_result(result, args.show_history))
                if args.context_json:
                    atomic_json(args.context_json, result)
                return 0
            print("AI Service Desk | LOCAL | historicos nao validados")
            print("Digite /sair para encerrar. Cada pergunta e um novo atendimento, sem memoria.")
            while True:
                try:
                    text = input("\nDescreva o problema: ").strip()
                except EOFError:
                    break
                if text.lower() in ("/sair", "sair", "quit", "exit"):
                    break
                if not text:
                    continue
                try:
                    print(format_result(engine.search(text), args.show_history))
                except (ValueError, RuntimeError, OSError) as exc:
                    print("Consulta interrompida: " + str(exc))
            return 0
    except KeyboardInterrupt:
        print("\nInterrompido. Lotes ja confirmados podem ser retomados.")
        return 130
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()
    return 0
