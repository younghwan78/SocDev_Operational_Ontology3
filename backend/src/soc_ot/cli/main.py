import argparse
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from soc_ot import __version__
from soc_ot.agents.codex_cli_provider import CodexCliProvider
from soc_ot.agents.providers import OpenAIResponsesProvider, ReviewProvider
from soc_ot.application.contracts import export_contracts
from soc_ot.application.evaluation import run_evaluation
from soc_ot.application.evaluation_artifacts import write_evaluation_artifacts
from soc_ot.application.evaluation_manifest import (
    DEFAULT_EVALUATION_RELEASE,
    freeze_evaluation_manifest,
    manifest_partitions,
    validate_evaluation_manifest,
)
from soc_ot.application.live_evaluation import (
    estimate_ablation_batch,
    estimate_stability_batch,
    run_live_ablation,
    run_live_stability,
)
from soc_ot.application.repositories import PostgresCaseRepository
from soc_ot.application.usability_study import (
    ParticipantKind,
    StudyCondition,
    create_session_template,
    load_protocol,
    load_session,
    render_baseline_markdown,
    render_study_report,
    summarize_sessions,
    validate_session,
    validate_study_materials,
    write_session_template,
)
from soc_ot.config import get_settings
from soc_ot.infrastructure.database import get_outcome_engine, get_runtime_engine
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.hidden_repository import PostgresHiddenCaseRepository
from soc_ot.infrastructure.project_repository import PostgresProjectRepository
from soc_ot.infrastructure.tables import HiddenAuthoringAuditRow

ROOT_DIR = Path(__file__).resolve().parents[4]
DEFAULT_EVALUATION_MANIFEST = (
    ROOT_DIR / f"fixtures/manifests/{DEFAULT_EVALUATION_RELEASE}.yaml"
)
DEFAULT_USABILITY_PROTOCOL = ROOT_DIR / "fixtures/usability/UX-H-20260719.protocol.yaml"
DEFAULT_BASELINE_PACK = (
    ROOT_DIR / "fixtures/usability/CASE-VR-001.baseline-pack.v1.yaml"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="soc-ot")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Show the implemented stage")

    contracts = subparsers.add_parser("contracts")
    contracts_sub = contracts.add_subparsers(dest="contracts_command")
    export = contracts_sub.add_parser("export")
    export.add_argument("--check", action="store_true")
    openapi_export = contracts_sub.add_parser("export-openapi")
    openapi_export.add_argument(
        "--output", type=Path, default=ROOT_DIR / "contracts/generated/openapi.json"
    )
    openapi_export.add_argument("--check", action="store_true")

    fixtures = subparsers.add_parser("fixtures")
    fixtures_sub = fixtures.add_subparsers(dest="fixtures_command")
    validate = fixtures_sub.add_parser("validate")
    validate.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    validate.add_argument("--case-id")
    validate.add_argument("--include-hidden", action="store_true")
    validate.add_argument(
        "--corpus",
        choices=["evaluation", "development", "projects", "all"],
        default="evaluation",
    )
    fixture_import = fixtures_sub.add_parser("import")
    fixture_import.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    fixture_import.add_argument("--case-id", required=True)
    fixture_import.add_argument("--replace-current", action="store_true")
    project_import = fixtures_sub.add_parser("import-project")
    project_import.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    project_import.add_argument("--project-id", required=True)
    project_import.add_argument("--replace-current", action="store_true")
    hidden_import = fixtures_sub.add_parser("import-hidden")
    hidden_import.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    hidden_import.add_argument("--case-id")

    dev = subparsers.add_parser("dev")
    dev_sub = dev.add_subparsers(dest="dev_command")
    inspect_hidden = dev_sub.add_parser("inspect-hidden")
    inspect_hidden.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    inspect_hidden.add_argument("--case-id", required=True)

    evaluation = subparsers.add_parser("evaluation")
    evaluation_sub = evaluation.add_subparsers(dest="evaluation_command")
    freeze = evaluation_sub.add_parser("freeze")
    freeze.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    freeze.add_argument(
        "--manifest", type=Path, default=DEFAULT_EVALUATION_MANIFEST
    )
    validate_release = evaluation_sub.add_parser("validate-release")
    validate_release.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    validate_release.add_argument(
        "--manifest", type=Path, default=DEFAULT_EVALUATION_MANIFEST
    )
    run = evaluation_sub.add_parser("run")
    run.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    run.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_EVALUATION_MANIFEST,
    )
    run.add_argument("--provider", choices=["replay"], default="replay")
    run.add_argument("--topology", choices=["B0", "B1", "B2", "B3"], default="B3")
    run.add_argument("--output-root", type=Path, default=ROOT_DIR / "output/evaluations")
    run.add_argument("--output", type=Path, help="Optional legacy summary JSON path")
    ablate = evaluation_sub.add_parser("ablate")
    ablate.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    ablate.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_EVALUATION_MANIFEST,
    )
    ablate.add_argument(
        "--provider", choices=["openai", "codex-cli"], default="openai"
    )
    ablate.add_argument("--partitions", default="validation,sealed-unseen")
    ablate.add_argument("--output-root", type=Path, default=ROOT_DIR / "output/evaluations")
    ablate.add_argument("--output", type=Path, help="Optional legacy summary JSON path")
    ablate.add_argument("--acknowledge-cost", action="store_true")
    ablate.add_argument("--acknowledge-usage", action="store_true")
    stability = evaluation_sub.add_parser("stability")
    stability.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    stability.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_EVALUATION_MANIFEST,
    )
    stability.add_argument(
        "--provider", choices=["openai", "codex-cli"], default="openai"
    )
    stability.add_argument(
        "--partition", choices=["validation", "sealed-unseen"], required=True
    )
    stability.add_argument(
        "--topology", choices=["B1", "B2", "B3"], required=True
    )
    stability.add_argument("--repeat", type=int, required=True)
    stability.add_argument("--output-root", type=Path, default=ROOT_DIR / "output/evaluations")
    stability.add_argument("--output", type=Path, help="Optional legacy summary JSON path")
    stability.add_argument("--acknowledge-cost", action="store_true")
    stability.add_argument("--acknowledge-usage", action="store_true")

    agent = subparsers.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="agent_command")
    preflight = agent_sub.add_parser("preflight")
    preflight.add_argument(
        "--provider", choices=["openai", "codex-cli"], default="openai"
    )

    usability = subparsers.add_parser("usability")
    usability_sub = usability.add_subparsers(dest="usability_command")
    usability_validate = usability_sub.add_parser("validate")
    _add_usability_material_arguments(usability_validate)
    prepare = usability_sub.add_parser("prepare-session")
    _add_usability_material_arguments(prepare)
    prepare.add_argument(
        "--condition",
        choices=[item.value for item in StudyCondition],
        required=True,
    )
    prepare.add_argument(
        "--participant-kind",
        choices=[item.value for item in ParticipantKind],
        required=True,
    )
    prepare.add_argument("--participant-code", required=True)
    prepare.add_argument("--session-id")
    prepare.add_argument("--output-root", type=Path, default=ROOT_DIR / "output/usability")
    prepare.add_argument("--force", action="store_true")
    session_validate = usability_sub.add_parser("validate-session")
    session_validate.add_argument("--protocol", type=Path, default=DEFAULT_USABILITY_PROTOCOL)
    session_validate.add_argument("--session", type=Path, required=True)
    session_validate.add_argument("--require-complete", action="store_true")
    summarize = usability_sub.add_parser("summarize")
    summarize.add_argument("--protocol", type=Path, default=DEFAULT_USABILITY_PROTOCOL)
    summarize.add_argument("--sessions-root", type=Path, required=True)
    summarize.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        print(
            "I7 Replay + Step 5 B2 stability gates complete; "
            "B2 durable dossier runtime active; UX-H session tooling ready, "
            "OPS-C project runtime/API ready, OPS-D product UX next; "
            "human gate pending"
        )
        return 0
    if args.command == "contracts" and args.contracts_command == "export":
        export_contracts(ROOT_DIR / "contracts/generated", check=args.check)
        print("Contracts are current." if args.check else "Contracts exported.")
        return 0
    if args.command == "contracts" and args.contracts_command == "export-openapi":
        from soc_ot.api.main import create_app
        from soc_ot.application.repositories import InMemoryCaseRepository
        from soc_ot.application.review_runs import InMemoryReviewRunRepository

        rendered = json.dumps(
            create_app(InMemoryCaseRepository(), InMemoryReviewRunRepository()).openapi(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        if args.check:
            if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
                raise ValueError("generated OpenAPI contract is stale")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print("OpenAPI contract is current." if args.check else "OpenAPI contract exported.")
        return 0
    if args.command == "fixtures" and args.fixtures_command == "validate":
        fixture_repository = FixtureRepository(args.root)
        if args.corpus == "projects":
            projects = fixture_repository.validate_project_corpus()
            if args.case_id:
                projects = [item for item in projects if item.project_id == args.case_id]
                if not projects:
                    raise ValueError(f"unknown project fixture: {args.case_id}")
            print(f"Validated {len(projects)} project fixture(s).")
            return 0
        if args.case_id:
            case_ids = [args.case_id]
        elif args.corpus == "development":
            case_ids = fixture_repository.development_case_ids()
        elif args.corpus == "all":
            case_ids = (
                fixture_repository.case_ids()
                + fixture_repository.development_case_ids()
            )
        else:
            case_ids = fixture_repository.case_ids()
        for case_id in case_ids:
            fixture_repository.validate_case(case_id, include_hidden=args.include_hidden)
        project_count = 0
        if args.corpus == "all":
            project_count = len(fixture_repository.validate_project_corpus())
        print(
            f"Validated {len(case_ids)} fixture case(s) and {project_count} project fixture(s)."
        )
        return 0
    if args.command == "fixtures" and args.fixtures_command == "import":
        fixture_repository = FixtureRepository(args.root)
        case = fixture_repository.validate_case(args.case_id)
        case_repository = PostgresCaseRepository(get_runtime_engine())
        current = case_repository.get(case.case_id)
        if (
            current
            and current.case.fixture_version == case.fixture_version
            and not args.replace_current
        ):
            print(f"Fixture {case.case_id} version {case.fixture_version} already imported.")
            return 0
        expected_version = current.aggregate_version if current else None
        stored = case_repository.save(
            case,
            event_type="fixture_reimported" if current else "fixture_imported",
            expected_aggregate_version=expected_version,
        )
        print(f"Imported {case.case_id} at aggregate version {stored.aggregate_version}.")
        return 0
    if args.command == "fixtures" and args.fixtures_command == "import-project":
        fixture_repository = FixtureRepository(args.root)
        projects = fixture_repository.validate_project_corpus()
        project = next(
            (item for item in projects if item.project_id == args.project_id),
            None,
        )
        if project is None:
            raise ValueError(f"unknown project fixture: {args.project_id}")
        fixture_hash = hashlib.sha256(
            (args.root / f"projects/{project.project_id}.yaml").read_bytes()
        ).hexdigest()
        project_repository = PostgresProjectRepository(get_runtime_engine())
        project_current = project_repository.get(project.project_id)
        if project_current and project.fixture_version < project_current.project.fixture_version:
            raise ValueError("PROJECT_FIXTURE_VERSION_REGRESSION")
        if (
            project_current
            and project.fixture_version == project_current.project.fixture_version
            and fixture_hash != project_current.fixture_hash
        ):
            raise ValueError("PROJECT_FIXTURE_VERSION_REUSED")
        if (
            project_current
            and project_current.project.fixture_version == project.fixture_version
            and not args.replace_current
        ):
            print(
                f"Project {project.project_id} version {project.fixture_version} "
                "already imported."
            )
            return 0
        project_stored = project_repository.save(
            project,
            expected_aggregate_version=(
                project_current.aggregate_version if project_current else None
            ),
            fixture_hash=fixture_hash,
        )
        print(
            f"Imported project {project.project_id} at aggregate version "
            f"{project_stored.aggregate_version}."
        )
        return 0
    if args.command == "fixtures" and args.fixtures_command == "import-hidden":
        settings = get_settings()
        if not settings.authoring_mode:
            print("Hidden import requires SOC_OT_AUTHORING_MODE=1.")
            return 2
        fixtures = FixtureRepository(args.root)
        case_ids = [args.case_id] if args.case_id else fixtures.case_ids()
        repository = PostgresHiddenCaseRepository(get_outcome_engine())
        print("=== AUTHORING/HIDDEN: hidden fixture import is being audited ===")
        for case_id in case_ids:
            repository.upsert(fixtures.load_hidden(case_id))
            _audit_hidden_access("import-hidden", case_id)
        print(f"Imported {len(case_ids)} hidden case(s) through the outcome-only port.")
        return 0
    if args.command == "dev" and args.dev_command == "inspect-hidden":
        settings = get_settings()
        if not settings.authoring_mode:
            print("Hidden inspection requires SOC_OT_AUTHORING_MODE=1.")
            return 2
        hidden = FixtureRepository(args.root).load_hidden(args.case_id)
        print("=== AUTHORING/HIDDEN: hidden fixture inspection is being audited ===")
        _audit_hidden_access("inspect-hidden", args.case_id)
        print(json.dumps(hidden.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0
    if args.command == "usability" and args.usability_command == "validate":
        protocol, pack, _ = validate_study_materials(
            args.root, args.protocol, args.baseline_pack
        )
        print(
            f"Validated study={protocol.study_id}, tasks={len(protocol.tasks)}, "
            f"baseline_surfaces={len(pack.surfaces)}; human results not evaluated."
        )
        return 0
    if args.command == "usability" and args.usability_command == "prepare-session":
        protocol, pack, case = validate_study_materials(
            args.root, args.protocol, args.baseline_pack
        )
        session_id = args.session_id or f"UXH-{uuid4()}"
        session_dir = args.output_root / session_id
        baseline_path = session_dir / "baseline-pack.md"
        session_path = session_dir / "session.yaml"
        if not args.force and (baseline_path.exists() or session_path.exists()):
            print("Session artifacts already exist; use --force to replace them.")
            return 2
        session = create_session_template(
            protocol,
            session_id=session_id,
            condition=StudyCondition(args.condition),
            participant_code=args.participant_code,
            participant_kind=ParticipantKind(args.participant_kind),
        )
        session_dir.mkdir(parents=True, exist_ok=True)
        if session.condition is StudyCondition.BASELINE:
            baseline_path.write_text(
                render_baseline_markdown(protocol, pack, case), encoding="utf-8"
            )
        write_session_template(session, session_path)
        print(
            f"Prepared draft session={session_id}; condition={session.condition}; "
            f"artifacts={session_dir}; no human observation recorded."
        )
        return 0
    if args.command == "usability" and args.usability_command == "validate-session":
        protocol = load_protocol(args.protocol)
        session = validate_session(
            protocol,
            load_session(args.session),
            require_complete=args.require_complete,
        )
        print(
            f"Validated session={session.session_id}; status={session.status}; "
            f"participant_kind={session.participant_kind}."
        )
        return 0
    if args.command == "usability" and args.usability_command == "summarize":
        protocol = load_protocol(args.protocol)
        session_paths = sorted(args.sessions_root.rglob("session.yaml"))
        sessions = [load_session(path) for path in session_paths]
        summary = summarize_sessions(
            protocol, sessions, generated_at=datetime.now(UTC)
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        report_path = args.output.with_name("report.md")
        report_path.write_text(render_study_report(summary), encoding="utf-8")
        print(
            f"Summarized sessions={len(sessions)}; "
            f"human_gate_status={summary.human_gate_status}; "
            f"interpretation={summary.interpretation}; artifacts={args.output.parent}."
        )
        return 0
    if args.command == "evaluation" and args.evaluation_command == "freeze":
        manifest = freeze_evaluation_manifest(args.root, args.manifest)
        print(f"Frozen {len(manifest.cases)} evaluation cases.")
        return 0
    if args.command == "evaluation" and args.evaluation_command == "validate-release":
        validate_evaluation_manifest(args.root, args.manifest)
        print("Evaluation release is current.")
        return 0
    if args.command == "evaluation" and args.evaluation_command == "run":
        manifest = validate_evaluation_manifest(args.root, args.manifest)
        replay_summary = run_evaluation(
            FixtureRepository(args.root), topology=args.topology, manifest=manifest
        )
        artifact_dir = write_evaluation_artifacts(
            replay_summary,
            manifest_path=args.manifest,
            output_root=args.output_root,
            provider="replay",
            model_identifier="deterministic-replay",
            runtime_settings=_redacted_runtime_settings(),
        )
        if args.output is not None:
            _write_legacy_summary(args.output, replay_summary.model_dump(mode="json"))
        print(
            f"Evaluation passed {replay_summary.passed}/{replay_summary.total}; "
            f"artifacts={artifact_dir}"
        )
        return 0 if replay_summary.passed == replay_summary.total else 1
    if args.command == "agent" and args.agent_command == "preflight":
        settings = get_settings()
        if args.provider == "codex-cli":
            try:
                cli_provider = CodexCliProvider(
                    model=settings.codex_cli_model,
                    reasoning_effort=settings.codex_cli_reasoning_effort,
                    timeout_seconds=settings.codex_cli_timeout_seconds,
                )
                cli_provider.preflight()
            except ValueError as error:
                print(f"Codex CLI preflight failed: {error}")
                return 2
            print(
                "Codex CLI preflight passed: "
                f"model={cli_provider.model}, effort={cli_provider.reasoning_effort}, "
                "billing=ChatGPT subscription."
            )
            return 0
        problems = []
        if not settings.openai_api_key:
            problems.append("OPENAI_API_KEY is missing")
        if not settings.role_model:
            problems.append("SOC_OT_ROLE_MODEL is missing")
        if settings.max_case_cost_usd <= 0 or settings.max_evaluation_cost_usd <= 0:
            problems.append("cost budgets must be positive")
        if (
            settings.role_input_cost_per_million_usd <= 0
            or settings.role_output_cost_per_million_usd <= 0
        ):
            problems.append("live token price settings must be positive")
        if problems:
            print("Live preflight failed: " + "; ".join(problems))
            return 2
        print("Live preflight passed without exposing credentials.")
        return 0
    if args.command == "evaluation" and args.evaluation_command in {"ablate", "stability"}:
        settings = get_settings()
        is_codex_cli = args.provider == "codex-cli"
        if is_codex_cli and not args.acknowledge_usage:
            print(
                "Use --acknowledge-usage after reviewing the ChatGPT subscription "
                "call/token envelope."
            )
            return 2
        if not is_codex_cli and not args.acknowledge_cost:
            print("Use --acknowledge-cost after reviewing the evaluation budget.")
            return 2
        manifest = validate_evaluation_manifest(args.root, args.manifest)
        partitions = manifest_partitions(manifest)
        estimate_case_cost = 0.0 if is_codex_cli else settings.max_case_cost_usd
        estimate_batch_cost = 0.0 if is_codex_cli else settings.max_evaluation_cost_usd
        if args.evaluation_command == "ablate":
            if args.partitions != "validation,sealed-unseen":
                print("Ablation requires exactly validation,sealed-unseen partitions.")
                return 2
            estimate = estimate_ablation_batch(
                max_case_cost_usd=estimate_case_cost,
                max_evaluation_cost_usd=estimate_batch_cost,
                case_timeout_seconds=settings.max_case_runtime_seconds,
                manifest=manifest,
            )
        else:
            estimate = estimate_stability_batch(
                args.partition,
                args.repeat,
                topology=args.topology,
                max_case_cost_usd=estimate_case_cost,
                max_evaluation_cost_usd=estimate_batch_cost,
                case_timeout_seconds=settings.max_case_runtime_seconds,
                manifest=manifest,
            )
        cost_text = (
            "billing=ChatGPT subscription; USD cost=N/A"
            if is_codex_cli
            else f"maximum_cost=${estimate.maximum_cost_usd:.2f}"
        )
        print(
            f"Live batch estimate: runs={estimate.run_count}, "
            f"semantic_calls={estimate.semantic_call_count}, "
            f"timeout_seconds={estimate.timeout_envelope_seconds}, {cost_text}"
        )
        if not estimate.within_budget:
            print("Batch estimate exceeds SOC_OT_MAX_EVALUATION_COST_USD; aborting before call.")
            return 2
        evaluation_provider: ReviewProvider
        if is_codex_cli:
            evaluation_provider = CodexCliProvider(
                model=settings.codex_cli_model,
                reasoning_effort=settings.codex_cli_reasoning_effort,
                timeout_seconds=settings.codex_cli_timeout_seconds,
            )
            evaluation_provider.preflight()
            max_cost_usd = 0.0
            max_workers = settings.codex_cli_parallelism
            model_identifier = settings.codex_cli_model
        else:
            if not settings.openai_api_key:
                print("OPENAI_API_KEY is required for live evaluation.")
                return 2
            evaluation_provider = OpenAIResponsesProvider(
                api_key=settings.openai_api_key,
                model=settings.role_model,
                challenger_model=settings.challenger_model,
                chair_model=settings.chair_model,
                input_cost_per_million_usd=settings.role_input_cost_per_million_usd,
                output_cost_per_million_usd=settings.role_output_cost_per_million_usd,
            )
            max_cost_usd = settings.max_evaluation_cost_usd
            max_workers = 1
            model_identifier = settings.role_model
        if args.evaluation_command == "ablate":
            ablation_summary = run_live_ablation(
                FixtureRepository(args.root),
                evaluation_provider,
                max_cost_usd=max_cost_usd,
                max_workers=max_workers,
                manifest=manifest,
            )
            success = ablation_summary.release_gate_passed
            result_line = (
                "Live ablation B2/B1="
                f"{len(ablation_summary.b2_over_b1.marginal_case_ids)}/"
                f"{len(partitions['validation']) + len(partitions['sealed-unseen'])}; "
                "B3/B2="
                f"{len(ablation_summary.b3_over_b2.marginal_case_ids)}/"
                f"{len(partitions['validation']) + len(partitions['sealed-unseen'])}; "
                f"selected={ablation_summary.selected_topology}; "
                f"stop_rule={ablation_summary.stop_rule}"
            )
            summary_payload = ablation_summary.model_dump(mode="json")
            actual_cost = ablation_summary.estimated_cost_usd
        else:
            stability_summary = run_live_stability(
                FixtureRepository(args.root),
                evaluation_provider,
                topology=args.topology,
                partition=args.partition,
                repeats=args.repeat,
                max_cost_usd=max_cost_usd,
                max_workers=max_workers,
                manifest=manifest,
            )
            success = stability_summary.stability_gate_passed
            result_line = (
                f"Live stability topology={stability_summary.topology}; "
                f"acceptable={stability_summary.acceptable_runs}/"
                f"{stability_summary.total_runs}; "
                f"policy={stability_summary.policy_compliant_runs}/"
                f"{stability_summary.total_runs}"
            )
            summary_payload = stability_summary.model_dump(mode="json")
            actual_cost = stability_summary.estimated_cost_usd
        evaluation_result = (
            ablation_summary if args.evaluation_command == "ablate" else stability_summary
        )
        runtime_settings = _redacted_runtime_settings()
        runtime_settings.update(
            {
                "llm_mode": "codex-cli" if is_codex_cli else "openai",
                "evaluation_surface": "codex-cli" if is_codex_cli else "responses-api",
                "model_identifier": model_identifier,
                "adapter_prompt_contract_version": (
                    "codex-cli-i7c.v1" if is_codex_cli else None
                ),
                "reasoning_effort": (
                    settings.codex_cli_reasoning_effort if is_codex_cli else None
                ),
                "billing_basis": (
                    "chatgpt-subscription" if is_codex_cli else "api-token-rates"
                ),
                "parallelism": max_workers,
                "evaluation_topology": (
                    args.topology if args.evaluation_command == "stability" else None
                ),
            }
        )
        artifact_dir = write_evaluation_artifacts(
            evaluation_result,
            manifest_path=args.manifest,
            output_root=args.output_root,
            provider=evaluation_provider.name,
            model_identifier=model_identifier,
            runtime_settings=runtime_settings,
            batch_estimate=estimate,
        )
        if args.output is not None:
            _write_legacy_summary(args.output, summary_payload)
        if is_codex_cli:
            input_tokens = sum(
                item.ablation.input_tokens for item in evaluation_result.results
            )
            output_tokens = sum(
                item.ablation.output_tokens for item in evaluation_result.results
            )
            usage_text = (
                f"ChatGPT subscription tokens input={input_tokens}, "
                f"output={output_tokens}"
            )
        else:
            usage_text = f"estimated cost=${actual_cost:.4f}"
        print(f"{result_line}; {usage_text}; artifacts={artifact_dir}")
        return 0 if success else 1
    parser.print_help()
    return 0


def _redacted_runtime_settings() -> dict[str, object]:
    settings = get_settings()
    return {
        "environment": settings.env,
        "llm_mode": settings.llm_mode,
        "max_case_runtime_seconds": settings.max_case_runtime_seconds,
        "role_timeout_seconds": settings.role_timeout_seconds,
        "max_case_cost_usd": settings.max_case_cost_usd,
        "max_evaluation_cost_usd": settings.max_evaluation_cost_usd,
        "raw_provider_retention_days": settings.raw_provider_retention_days,
    }


def _add_usability_material_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=ROOT_DIR / "fixtures")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_USABILITY_PROTOCOL)
    parser.add_argument(
        "--baseline-pack",
        type=Path,
        default=DEFAULT_BASELINE_PACK,
    )


def _write_legacy_summary(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _audit_hidden_access(action: str, case_id: str) -> None:
    settings = get_settings()
    with Session(get_outcome_engine()) as session, session.begin():
        session.add(
            HiddenAuthoringAuditRow(
                audit_id=str(uuid4()),
                actor_id=settings.local_actor_id,
                action=action,
                case_id=case_id,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
