from dataclasses import dataclass, field, replace
from enum import StrEnum

RECENT_TURN_LIMIT = 8


class FactAuthority(StrEnum):
    MODEL_INFERRED = "MODEL_INFERRED"
    USER_EXPLICIT = "USER_EXPLICIT"
    BACKEND = "BACKEND"
    TRUSTED_SESSION = "TRUSTED_SESSION"


class TurnRelation(StrEnum):
    NEW_GOAL = "NEW_GOAL"
    CONTINUATION = "CONTINUATION"
    CORRECTION = "CORRECTION"
    ANSWER_TO_PENDING = "ANSWER_TO_PENDING"
    CONFIRMATION = "CONFIRMATION"
    NEGATION = "NEGATION"
    TOPIC_SWITCH = "TOPIC_SWITCH"


@dataclass(frozen=True)
class ConversationField:
    value: str = ""
    authority: FactAuthority = FactAuthority.MODEL_INFERRED


@dataclass(frozen=True)
class ConversationFact:
    key: str
    value: str
    authority: FactAuthority


@dataclass(frozen=True)
class ConversationFactProposal:
    key: str
    value: str
    source: FactAuthority


@dataclass(frozen=True)
class TrustedConversationContext:
    identity_id: str
    name: str
    email: str
    area: str
    role: str
    job_title: str = "Colaborador"


@dataclass(frozen=True)
class DialogueState:
    domain: str = "UNKNOWN"
    goal: ConversationField = field(default_factory=ConversationField)
    intent: ConversationField = field(
        default_factory=lambda: ConversationField(
            "OUTRO",
            FactAuthority.MODEL_INFERRED,
        )
    )
    system: ConversationField = field(default_factory=ConversationField)
    product: ConversationField = field(default_factory=ConversationField)
    stage: str = "IDLE"
    pending_information: tuple[str, ...] = ()
    last_question: str = ""


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    text: str


@dataclass(frozen=True)
class ConversationContext:
    trusted: TrustedConversationContext
    dialogue: DialogueState = field(default_factory=DialogueState)
    facts: tuple[ConversationFact, ...] = ()
    recent_turns: tuple[ConversationTurn, ...] = ()

    def fact(self, key: str) -> ConversationFact | None:
        return next((item for item in self.facts if item.key == key), None)


@dataclass(frozen=True)
class ConversationDelta:
    relation: TurnRelation
    domain: str
    goal: str
    intent: str
    entities: dict[str, str]
    facts_added: tuple[ConversationFactProposal, ...]
    facts_corrected: tuple[ConversationFactProposal, ...]
    answered_pending_question: bool
    semantic_signal: str
    understood_topic: str


_AUTHORITY_RANK = {
    FactAuthority.MODEL_INFERRED: 0,
    FactAuthority.USER_EXPLICIT: 1,
    FactAuthority.BACKEND: 2,
    FactAuthority.TRUSTED_SESSION: 3,
}

_CONVERSATIONAL_FIELDS = frozenset(
    {
        "goal",
        "intent",
        "system",
        "product",
    }
)

_PROTECTED_KEYS = frozenset(
    {
        "identity_id",
        "name",
        "email",
        "area",
        "job_title",
        "cargo",
        "role",
        "user_role",
        "requested_role",
        "policy",
        "request_id",
        "request_state",
        "approval",
        "approval_status",
        "routing",
        "execution",
        "knowledge_id",
        "support_handoff_id",
        "support_handoff_system",
        "support_handoff_capability",
        "support_technician_id",
    }
)


def _can_replace(current, proposed):
    return _AUTHORITY_RANK[proposed] >= _AUTHORITY_RANK[current]


def _merge_field(current, value, source):
    value = str(value).strip()
    if not value or not _can_replace(current.authority, source):
        return current
    return ConversationField(value, source)


def _merge_fact(facts, proposal):
    current = {item.key: item for item in facts}
    existing = current.get(proposal.key)
    if existing is None or _can_replace(existing.authority, proposal.source):
        current[proposal.key] = ConversationFact(
            proposal.key,
            proposal.value.strip(),
            proposal.source,
        )
    return tuple(current[key] for key in sorted(current))


def reduce_conversation_context(context, delta, *, user_message):
    dialogue = DialogueState() if delta.relation == TurnRelation.TOPIC_SWITCH else context.dialogue
    dialogue = replace(
        dialogue,
        domain=delta.domain,
        goal=_merge_field(
            dialogue.goal,
            delta.goal,
            FactAuthority.MODEL_INFERRED,
        ),
        intent=_merge_field(
            dialogue.intent,
            delta.intent,
            FactAuthority.MODEL_INFERRED,
        ),
        system=_merge_field(
            dialogue.system,
            delta.entities.get("system", ""),
            FactAuthority.MODEL_INFERRED,
        ),
        product=_merge_field(
            dialogue.product,
            delta.entities.get("product", ""),
            FactAuthority.MODEL_INFERRED,
        ),
        pending_information=(
            () if delta.answered_pending_question else dialogue.pending_information
        ),
    )

    facts = context.facts
    for proposal in (*delta.facts_added, *delta.facts_corrected):
        if proposal.key in _PROTECTED_KEYS:
            continue
        if proposal.source not in {
            FactAuthority.USER_EXPLICIT,
            FactAuthority.MODEL_INFERRED,
        }:
            continue
        if proposal.key in _CONVERSATIONAL_FIELDS:
            dialogue = replace(
                dialogue,
                **{
                    proposal.key: _merge_field(
                        getattr(dialogue, proposal.key),
                        proposal.value,
                        proposal.source,
                    )
                },
            )
        else:
            facts = _merge_fact(facts, proposal)

    return replace(
        context,
        dialogue=dialogue,
        facts=facts,
    )


def new_conversation_context(identity_id, name, email, area, role, job_title="Colaborador"):
    return ConversationContext(
        trusted=TrustedConversationContext(
            identity_id,
            name,
            email,
            area,
            role,
            job_title,
        )
    )


def append_turn(context, role, text):
    turn = ConversationTurn(
        role=role,
        text=text.strip(),
    )
    return replace(
        context,
        recent_turns=(*context.recent_turns, turn)[-RECENT_TURN_LIMIT:],
    )


def apply_backend_updates(context, updates):
    facts = context.facts
    for key, value in updates.items():
        if value is not None and str(value).strip():
            facts = _merge_fact(
                facts,
                ConversationFactProposal(
                    key,
                    str(value),
                    FactAuthority.BACKEND,
                ),
            )
    return replace(
        context,
        facts=facts,
    )
