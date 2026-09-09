from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from ai_service_desk.engine.access_request import prepare_access_request
from ai_service_desk.engine.approval import ApprovalService
from ai_service_desk.engine.cdm_execution import CDMActionExecutor
from ai_service_desk.engine.classification import classify_ticket
from ai_service_desk.engine.execution import ExecutionEngine
from ai_service_desk.engine.knowledge import build_knowledge_index
from ai_service_desk.engine.knowledge_retrieval import KnowledgeEngine
from ai_service_desk.engine.learning_prevention import (
    InMemoryOutcomeStore,
    OpportunityEngine,
    OutcomeCollector,
    PatternAggregator,
)
from ai_service_desk.engine.ollama import OllamaClient, OllamaError
from ai_service_desk.engine.playbook import build_playbook_catalog
from ai_service_desk.engine.playbook_resolution import (
    PlaybookEngine,
    action_proposal_descriptor,
)
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.routing import (
    ApprovalQueue,
    InMemoryRoutingAssignmentStore,
    RoutedRequestService,
    RoutingAssignmentNotFoundError,
    RoutingRegistry,
    RoutingRule,
    RoutingService,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianRegistryEntry,
)
from ai_service_desk.engine.triage import TriageEngine
from ai_service_desk.integrations.cdm import CDMAdapter
from ai_service_desk.integrations.cdm_fake_api import CDMFakeStore, build_cdm_server
from ai_service_desk.web.conversation import greeting_message, is_social_greeting
from ai_service_desk.web.demo_ai import DemoClassifierClient, DemoEmbedder
from ai_service_desk.web.demo_data import (
    demo_outcomes,
    write_demo_knowledge,
    write_demo_playbooks,
)
from ai_service_desk.web.demo_identity import DemoIdentityProvider, IdentityNotFoundError
from ai_service_desk.web.errors import WebDemoError
from ai_service_desk.web.presentation import present_prevention, present_request

DEMO_MODES = frozenset({"DETERMINISTIC", "LOCAL_AI"})
DEFAULT_DEMO_MODE = "DETERMINISTIC"


class DemoRuntime:
    def __init__(
        self,
        *,
        mode: str = DEFAULT_DEMO_MODE,
        fail_cdm_request_ids: set[str] | frozenset[str] | None = None,
    ) -> None:
        if mode not in DEMO_MODES:
            raise ValueError(f"Modo de demo invalido: {mode!r}.")
        self._ollama_client = None
        if mode == "LOCAL_AI":
            client = OllamaClient()
            try:
                client.model_info("qwen3.5:4b")
            except OllamaError as exc:
                client.close()
                raise WebDemoError(
                    "LOCAL_AI_UNAVAILABLE",
                    "Não foi possível validar o modelo local qwen3.5:4b no Ollama.",
                ) from exc
            self._ollama_client = client
        self.mode = mode
        self.identity_provider = DemoIdentityProvider()
        self._fail_cdm_request_ids = frozenset(fail_cdm_request_ids or ())
        self._temp = None
        self.fake_cdm_server = None
        self._fake_cdm_thread = None
        try:
            self.reset()
        except Exception:
            self.close()
            raise

    @classmethod
    def create(
        cls,
        *,
        mode: str = DEFAULT_DEMO_MODE,
        fail_cdm_request_ids: set[str] | frozenset[str] | None = None,
    ) -> DemoRuntime:
        return cls(mode=mode, fail_cdm_request_ids=fail_cdm_request_ids)

    def _close_knowledge_resources(self) -> None:
        triage = getattr(self, "_triage", None)
        if triage is not None:
            triage.clear()

        knowledge_engine = getattr(self, "knowledge_engine", None)
        if knowledge_engine is None:
            return
        matrix = getattr(knowledge_engine, "matrix", None)
        mapping = getattr(matrix, "_mmap", None)
        if mapping is not None and not mapping.closed:
            mapping.close()
        self.knowledge_engine = None

    def _close_mutable_resources(self) -> None:
        if self.fake_cdm_server is not None:
            self.fake_cdm_server.shutdown()
            self.fake_cdm_server.server_close()
            self.fake_cdm_server = None
        if self._fake_cdm_thread is not None:
            self._fake_cdm_thread.join(timeout=2)
            self._fake_cdm_thread = None
        self._close_knowledge_resources()
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None

    def reset(self) -> None:
        self._close_mutable_resources()
        self._temp = TemporaryDirectory(prefix="jup-resolve-demo-")
        root = Path(self._temp.name)
        knowledge_source = write_demo_knowledge(root / "knowledge.jsonl")
        playbook_source = write_demo_playbooks(root / "playbooks.jsonl")
        knowledge_index = root / "knowledge-index"
        playbook_catalog = root / "playbook-catalog"

        self.demo_embedder = DemoEmbedder()
        self.demo_classifier_client = DemoClassifierClient()
        build_knowledge_index(knowledge_source, knowledge_index, self.demo_embedder, batch_size=2)
        build_playbook_catalog(playbook_source, knowledge_index, playbook_catalog)
        self.knowledge_engine = KnowledgeEngine(
            knowledge_index,
            self.demo_classifier_client,
            self.demo_embedder,
        )
        self.playbook_engine = PlaybookEngine(playbook_catalog, knowledge_index)

        self.request_repository = InMemoryRequestRepository()
        self.routing_store = InMemoryRoutingAssignmentStore()
        self.conversations: dict[str, list[dict]] = {}
        self._triage: dict[str, tuple[TriageEngine, object]] = {}
        self.created_request_ids: list[str] = []
        self.request_metadata: dict[str, dict] = {}

        technician = self.identity_provider.technician_identity("tecnico-cdm")
        self.authorization_registry = TechnicianAuthorizationRegistry(
            [
                TechnicianRegistryEntry(
                    identity=technician,
                    capabilities=self.identity_provider.technician_capabilities("tecnico-cdm"),
                )
            ]
        )
        routing_registry = RoutingRegistry(
            [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)],
            self.authorization_registry,
        )
        self.policy_engine = PolicyEngine()
        self.lifecycle = RequestLifecycleService(self.request_repository, self.policy_engine)
        self.routed_requests = RoutedRequestService(
            self.lifecycle,
            RoutingService(routing_registry, self.routing_store),
        )
        self.approval_queue = ApprovalQueue(self.request_repository, self.routing_store)
        self.approval_service = ApprovalService(
            self.request_repository,
            self.lifecycle,
            self.authorization_registry,
        )

        self.outcome_store = InMemoryOutcomeStore()
        for outcome in demo_outcomes():
            self.outcome_store.ingest(outcome)

        self.fake_cdm_store = CDMFakeStore()
        self.fake_cdm_server = build_cdm_server(
            "127.0.0.1",
            0,
            "phase12-demo-service-token",
            store=self.fake_cdm_store,
            fail_request_ids=self._fail_cdm_request_ids,
        )
        self._fake_cdm_thread = Thread(target=self.fake_cdm_server.serve_forever, daemon=True)
        self._fake_cdm_thread.start()
        host, port = self.fake_cdm_server.server_address[:2]
        adapter = CDMAdapter(
            f"http://{host}:{port}",
            "phase12-demo-service-token",
            timeout_seconds=2,
        )
        self.execution_engine = ExecutionEngine(
            self.request_repository,
            self.lifecycle,
            self.policy_engine,
            CDMActionExecutor(adapter),
        )

    def _new_triage(self, identity_id: str) -> tuple[TriageEngine, object]:
        session_id = f"demo-{identity_id}-{len(self.conversations.get(identity_id, [])) + 1}"

        def classifier(text):
            if self.mode == "LOCAL_AI":
                return classify_ticket(text, self._ollama_client.chat)
            return classify_ticket(text, self.demo_classifier_client.chat)

        engine = TriageEngine(session_id, self.knowledge_engine, classifier)
        return engine, engine.initial_state()

    def _requester(self, identity_id: str):
        try:
            return self.identity_provider.requester_identity(identity_id)
        except IdentityNotFoundError as exc:
            raise WebDemoError(
                "NOT_AUTHORIZED",
                "Perfil sem acesso à visão de solicitações.",
            ) from exc

    def _technician(self, identity_id: str):
        try:
            return self.identity_provider.technician_identity(identity_id)
        except IdentityNotFoundError as exc:
            raise WebDemoError("NOT_AUTHORIZED", "Perfil sem acesso à Operação.") from exc

    def _assignment_for_record(self, record):
        try:
            assignment = self.routing_store.get(record.request_id)
        except RoutingAssignmentNotFoundError as exc:
            raise WebDemoError(
                "ROUTING_INCONSISTENT",
                "Solicitação pendente sem routing operacional consistente.",
            ) from exc
        if (
            assignment.request_id != record.request_id
            or assignment.system != record.context.system
            or assignment.capability != record.context.capability
        ):
            raise WebDemoError(
                "ROUTING_INCONSISTENT",
                "Routing operacional diverge da solicitação.",
            )
        return assignment

    def _require_assigned_technician(self, identity_id: str, request_id: str):
        technician = self._technician(identity_id)
        record = self.request_repository.get(request_id)
        assignment = self._assignment_for_record(record)
        if assignment.technician != technician:
            raise WebDemoError(
                "NOT_AUTHORIZED",
                "Solicitação não está atribuída a este técnico.",
            )
        return technician, record, assignment

    def _present(self, record, *, assignment=None, include_internal=False) -> dict:
        return present_request(
            record,
            self.request_repository.audit_for(record.request_id),
            self.request_metadata.get(record.request_id, {}),
            assignment=assignment,
            include_internal=include_internal,
        )

    def _prevention_opportunities(self):
        patterns = PatternAggregator.aggregate(self.outcome_store.snapshot())
        return OpportunityEngine().generate(patterns)

    def send_message(self, identity_id: str, message: str) -> dict:
        requester = self._requester(identity_id)
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Mensagem vazia.")

        if is_social_greeting(message):
            chat = self._ollama_client.chat if self.mode == "LOCAL_AI" else None
            return {
                "status": "SOCIAL",
                "request_id": None,
                "assistant_message": greeting_message(message, requester.name, chat),
            }

        current = self._triage.get(identity_id)
        if current is None or current[1].status != "ACTIVE":
            current = self._new_triage(identity_id)
        engine, state = current
        next_state, knowledge_result = engine.step(state, message)
        self._triage[identity_id] = (engine, next_state)
        self.conversations.setdefault(identity_id, []).append(
            {"role": "USER", "text": message.strip(), "status": knowledge_result["status"]}
        )

        if knowledge_result["status"] != "KNOWLEDGE_FOUND":
            return {
                "status": knowledge_result["status"],
                "question": knowledge_result.get("question"),
                "reason": knowledge_result.get("reason"),
                "request_id": None,
            }

        knowledge = knowledge_result["knowledge"]
        playbook_result = self.playbook_engine.resolve(knowledge)
        if playbook_result["status"] == "KNOWLEDGE_ONLY":
            interaction_id = f"DEMO-KNOWLEDGE-{len(self.outcome_store.snapshot()) + 1:03d}"
            self.outcome_store.ingest(
                OutcomeCollector.from_knowledge(
                    interaction_id,
                    next_state,
                    knowledge_result,
                    area=requester.area,
                )
            )
            return {
                "status": "KNOWLEDGE_FOUND",
                "knowledge_id": knowledge["knowledge_id"],
                "answer": knowledge["answer"],
                "request_id": None,
            }

        if playbook_result["status"] != "PLAYBOOK_FOUND":
            return {
                "status": "PLAYBOOK_UNAVAILABLE",
                "reason": playbook_result["reason"],
                "request_id": None,
            }

        playbook = playbook_result["playbook"]
        step = next(
            (item for item in playbook["steps"] if item["type"] == "ACTION_PROPOSAL"),
            None,
        )
        if step is None:
            return {"status": "PLAYBOOK_GUIDANCE", "request_id": None}
        descriptor = action_proposal_descriptor(knowledge["knowledge_id"], playbook, step)
        preparation = prepare_access_request(requester, next_state, descriptor)
        if preparation.status != "READY" or preparation.context is None:
            return {
                "status": "NEEDS_CLARIFICATION",
                "reason": preparation.reason_code,
                "request_id": None,
            }

        record = self.routed_requests.create_request(preparation.context)
        self.created_request_ids.append(record.request_id)
        self.request_metadata[record.request_id] = {
            "classification_confidence": next_state.confidence,
            "source_interaction_id": next_state.session_id,
        }
        return {
            "status": "REQUEST_CREATED" if record.state == "PENDING_APPROVAL" else record.state,
            "request_id": record.request_id,
            "state": record.state,
            "confidence": record.confidence.level,
            "policy": record.creation_policy.decision,
        }

    def list_requests(self, identity_id: str) -> list[dict]:
        requester = self._requester(identity_id)
        items = []
        for request_id in self.created_request_ids:
            record = self.request_repository.get(request_id)
            if record.context.requester != requester:
                continue
            assignment = self.routing_store.get_optional(request_id)
            items.append(self._present(record, assignment=assignment))
        return items

    def get_request(self, identity_id: str, request_id: str) -> dict:
        requester = self._requester(identity_id)
        record = self.request_repository.get(request_id)
        if record.context.requester != requester:
            raise WebDemoError("NOT_AUTHORIZED", "Solicitação não pertence ao solicitante atual.")
        assignment = self.routing_store.get_optional(request_id)
        return self._present(record, assignment=assignment)

    def list_approvals(self, identity_id: str) -> list[dict]:
        technician = self._technician(identity_id)
        return [
            self._present(item.request, assignment=item.assignment, include_internal=True)
            for item in self.approval_queue.pending(technician_id=technician.technician_id)
        ]

    def get_operational_request(self, identity_id: str, request_id: str) -> dict:
        _, record, assignment = self._require_assigned_technician(identity_id, request_id)
        return self._present(record, assignment=assignment, include_internal=True)

    def approve_request(
        self,
        identity_id: str,
        request_id: str,
        *,
        expected_version: int,
    ) -> dict:
        technician, _, assignment = self._require_assigned_technician(identity_id, request_id)
        approved = self.approval_service.approve(
            request_id,
            technician,
            expected_version=expected_version,
        )
        final = self.execution_engine.execute(request_id, expected_version=approved.version)
        return self._present(final, assignment=assignment, include_internal=True)

    def reject_request(
        self,
        identity_id: str,
        request_id: str,
        *,
        expected_version: int,
    ) -> dict:
        technician, _, assignment = self._require_assigned_technician(identity_id, request_id)
        rejected = self.approval_service.reject(
            request_id,
            technician,
            expected_version=expected_version,
        )
        return self._present(rejected, assignment=assignment, include_internal=True)

    def list_prevention(self, identity_id: str) -> list[dict]:
        self._technician(identity_id)
        return [present_prevention(item) for item in self._prevention_opportunities()]

    def get_prevention(self, identity_id: str, opportunity_id: str) -> dict:
        self._technician(identity_id)
        for item in self._prevention_opportunities():
            if item.opportunity_id == opportunity_id:
                return present_prevention(item)
        raise WebDemoError(
            "PREVENTION_NOT_FOUND",
            "Oportunidade de prevenção não encontrada.",
        )

    def close(self) -> None:
        try:
            self._close_mutable_resources()
        finally:
            if self._ollama_client is not None:
                self._ollama_client.close()
                self._ollama_client = None
