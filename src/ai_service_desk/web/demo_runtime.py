from ai_service_desk.engine.learning_prevention import InMemoryOutcomeStore
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
from ai_service_desk.web.demo_data import demo_outcomes
from ai_service_desk.web.demo_identity import DemoIdentityProvider


class DemoRuntime:
    def __init__(self) -> None:
        self.identity_provider = DemoIdentityProvider()
        self.reset()

    @classmethod
    def create(cls) -> "DemoRuntime":
        return cls()

    def reset(self) -> None:
        self.request_repository = InMemoryRequestRepository()
        self.routing_store = InMemoryRoutingAssignmentStore()
        self.conversations: dict[str, list[dict]] = {}
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

        self.fake_cdm_store = None
        self.fake_cdm_server = None

    def close(self) -> None:
        server = self.fake_cdm_server
        if server is not None:
            server.shutdown()
            server.server_close()
            self.fake_cdm_server = None
