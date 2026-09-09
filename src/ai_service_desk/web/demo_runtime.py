from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from ai_service_desk.engine.access_request import prepare_access_request
from ai_service_desk.engine.classification import classify_ticket
from ai_service_desk.engine.knowledge import build_knowledge_index
from ai_service_desk.engine.knowledge_retrieval import KnowledgeEngine
from ai_service_desk.engine.learning_prevention import InMemoryOutcomeStore, OutcomeCollector
from ai_service_desk.engine.playbook import build_playbook_catalog
from ai_service_desk.engine.playbook_resolution import PlaybookEngine, action_proposal_descriptor
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.routing import (
    ApprovalQueue,
    InMemoryRoutingAssignmentStore,
    RoutedRequestService,
    RoutingRegistry,
    RoutingRule,
    RoutingService,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianRegistryEntry,
)
from ai_service_desk.engine.triage import TriageEngine
from ai_service_desk.integrations.cdm_fake_api import CDMFakeStore, build_cdm_server
from ai_service_desk.web.demo_ai import DemoClassifierClient, DemoEmbedder
from ai_service_desk.web.demo_data import demo_outcomes, write_demo_knowledge, write_demo_playbooks
from ai_service_desk.web.demo_identity import DemoIdentityProvider


class DemoRuntime:
    def __init__(self) -> None:
        self.identity_provider = DemoIdentityProvider()
        self._temp = None
        self.fake_cdm_server = None
        self._fake_cdm_thread = None
        self.reset()

    @classmethod
    def create(cls) -> "DemoRuntime":
        return cls()

    def _close_mutable_resources(self) -> None:
        if self.fake_cdm_server is not None:
            self.fake_cdm_server.shutdown()
            self.fake_cdm_server.server_close()
            self.fake_cdm_server = None
        if self._fake_cdm_thread is not None:
            self._fake_cdm_thread.join(timeout=2)
            self._fake_cdm_thread = None
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
        authorization = TechnicianAuthorizationRegistry(
            [
                TechnicianRegistryEntry(
                    identity=technician,
                    capabilities=self.identity_provider.technician_capabilities("tecnico-cdm"),
                )
            ]
        )
        routing_registry = RoutingRegistry(
            [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)], authorization
        )
        lifecycle = RequestLifecycleService(self.request_repository, PolicyEngine())
        self.routed_requests = RoutedRequestService(
            lifecycle,
            RoutingService(routing_registry, self.routing_store),
        )
        self.approval_queue = ApprovalQueue(self.request_repository, self.routing_store)

        self.outcome_store = InMemoryOutcomeStore()
        for outcome in demo_outcomes():
            self.outcome_store.ingest(outcome)

        self.fake_cdm_store = CDMFakeStore()
        self.fake_cdm_server = build_cdm_server(
            "127.0.0.1",
            0,
            "phase12-demo-service-token",
            store=self.fake_cdm_store,
        )
        self._fake_cdm_thread = Thread(target=self.fake_cdm_server.serve_forever, daemon=True)
        self._fake_cdm_thread.start()

    def _new_triage(self, identity_id: str) -> tuple[TriageEngine, object]:
        session_id = f"demo-{identity_id}-{len(self.conversations.get(identity_id, [])) + 1}"
        classifier = lambda text: classify_ticket(text, self.demo_classifier_client.chat)
        engine = TriageEngine(session_id, self.knowledge_engine, classifier)
        return engine, engine.initial_state()

    def send_message(self, identity_id: str, message: str) -> dict:
        requester = self.identity_provider.requester_identity(identity_id)
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Mensagem vazia.")

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

    def close(self) -> None:
        self._close_mutable_resources()
