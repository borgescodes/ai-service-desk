import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ai_service_desk.engine.access_request import (
    CDM_ACCESS_CAPABILITY,
    CDM_SYSTEM,
    CONCRETE_ROLES,
    AccessRequestContext,
    ConcreteRequestedRole,
    validate_access_request_context,
)
from ai_service_desk.engine.playbook import CAPABILITY_RE

PolicyDecisionValue = Literal["REQUIRE_APPROVAL", "DENY"]
POLICY_DECISIONS = frozenset({"REQUIRE_APPROVAL", "DENY"})
MACHINE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,119}$")


@dataclass(frozen=True)
class PolicyDecision:
    decision: PolicyDecisionValue
    policy_id: str
    reason_code: str
    reason: str


@dataclass(frozen=True)
class PolicyRule:
    system: str
    capability: str
    requested_role: ConcreteRequestedRole
    decision: PolicyDecisionValue
    policy_id: str
    reason_code: str
    reason: str


class PolicyConfigurationError(ValueError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def _invalid_rule(message: str) -> None:
    raise PolicyConfigurationError("POLICY_RULE_INVALID", message)


def _required_rule_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        _invalid_rule(f"{field} invalido na PolicyRule.")
    return value


def _validate_policy_rule(rule: object) -> PolicyRule:
    if not isinstance(rule, PolicyRule):
        _invalid_rule("Entrada de policy deve ser PolicyRule.")
    _required_rule_text(rule.system, "system", 120)
    capability = _required_rule_text(rule.capability, "capability", 120)
    if not CAPABILITY_RE.fullmatch(capability):
        _invalid_rule("capability invalida na PolicyRule.")
    if not isinstance(rule.requested_role, str) or rule.requested_role not in CONCRETE_ROLES:
        _invalid_rule("requested_role invalida na PolicyRule.")
    if not isinstance(rule.decision, str) or rule.decision not in POLICY_DECISIONS:
        _invalid_rule("decision invalida na PolicyRule.")
    policy_id = _required_rule_text(rule.policy_id, "policy_id", 120)
    if not MACHINE_CODE_RE.fullmatch(policy_id):
        _invalid_rule("policy_id invalido na PolicyRule.")
    reason_code = _required_rule_text(rule.reason_code, "reason_code", 120)
    if not MACHINE_CODE_RE.fullmatch(reason_code):
        _invalid_rule("reason_code invalido na PolicyRule.")
    _required_rule_text(rule.reason, "reason", 500)
    return rule


CDM_POLICY_RULES = (
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="SOLICITANTE",
        decision="REQUIRE_APPROVAL",
        policy_id="CDM_SOLICITANTE_ACCESS",
        reason_code="CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL",
        reason="Acesso de solicitante ao CDM exige aprovacao humana antes da execucao.",
    ),
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="APROVADOR",
        decision="DENY",
        policy_id="CDM_PRIVILEGED_ACCESS",
        reason_code="CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        reason="Roles privilegiados do CDM nao podem ser concedidos por este canal.",
    ),
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="ADMIN",
        decision="DENY",
        policy_id="CDM_PRIVILEGED_ACCESS",
        reason_code="CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        reason="Roles privilegiados do CDM nao podem ser concedidos por este canal.",
    ),
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="SUPERADMIN",
        decision="DENY",
        policy_id="CDM_PRIVILEGED_ACCESS",
        reason_code="CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        reason="Roles privilegiados do CDM nao podem ser concedidos por este canal.",
    ),
)


class PolicyEngine:
    def __init__(self, rules: Sequence[PolicyRule] | None = None):
        source = tuple(CDM_POLICY_RULES if rules is None else rules)
        validated = tuple(_validate_policy_rule(rule) for rule in source)

        index: dict[tuple[str, str, str], PolicyRule] = {}
        for rule in validated:
            key = (rule.system, rule.capability, rule.requested_role)
            if key in index:
                raise PolicyConfigurationError(
                    "POLICY_RULE_CONFLICT",
                    "Duas regras de policy possuem a mesma chave.",
                )
            index[key] = rule
        self._rules = index

    def evaluate(self, context: AccessRequestContext) -> PolicyDecision:
        validate_access_request_context(context)
        rule = self._rules.get((context.system, context.capability, context.requested_role))
        if rule is None:
            return PolicyDecision(
                decision="DENY",
                policy_id="FAIL_CLOSED_UNKNOWN_POLICY",
                reason_code="POLICY_NOT_FOUND",
                reason="Nenhuma policy conhecida autoriza este contexto.",
            )
        return PolicyDecision(
            decision=rule.decision,
            policy_id=rule.policy_id,
            reason_code=rule.reason_code,
            reason=rule.reason,
        )
