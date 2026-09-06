from dataclasses import dataclass


@dataclass(frozen=True)
class TicketClassification:
    intent: str
    system: str
    entities: dict[str, str]
    confidence: float
