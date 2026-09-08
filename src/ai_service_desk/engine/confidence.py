from dataclasses import dataclass
from typing import Literal

from ai_service_desk.engine.access_request import (
    CDM_ACCESS_CAPABILITY,
    CDM_ACCESS_INTENT,
    CDM_SYSTEM,
    AccessRequestContext,
    validate_access_request_context,
)
from ai_service_desk.engine.validation import normalize_text

CONTEXT_NOT_CDM_ACCESS_REQUEST = "CONTEXT_NOT_CDM_ACCESS_REQUEST"
AREA_MATCH_REVENDA = "AREA_MATCH_REVENDA"
AREA_OUTSIDE_REVENDA = "AREA_OUTSIDE_REVENDA"
PURPOSE_MATCH_MATERIAL_REQUEST = "PURPOSE_MATCH_MATERIAL_REQUEST"
PURPOSE_NOT_CONFIRMED = "PURPOSE_NOT_CONFIRMED"

MATERIAL_PURPOSE_PHRASES = (
    "solicitar material",
    "solicitar materiais",
    "solicitacao de material",
    "solicitacao de materiais",
)


@dataclass(frozen=True)
class ConfidenceAssessment:
    level: Literal["HIGH", "LOW"]
    reason_codes: tuple[str, ...]


def _is_cdm_access_context(context: AccessRequestContext) -> bool:
    return (
        context.system == CDM_SYSTEM
        and context.intent == CDM_ACCESS_INTENT
        and context.capability == CDM_ACCESS_CAPABILITY
    )


def _area_matches_revenda(area: str) -> bool:
    return "revenda" in normalize_text(area).split()


def _purpose_matches_material_request(purpose: str) -> bool:
    normalized = f" {normalize_text(purpose)} "
    return any(f" {phrase} " in normalized for phrase in MATERIAL_PURPOSE_PHRASES)


def assess_confidence(context: AccessRequestContext) -> ConfidenceAssessment:
    validate_access_request_context(context)
    if not _is_cdm_access_context(context):
        return ConfidenceAssessment("LOW", (CONTEXT_NOT_CDM_ACCESS_REQUEST,))

    area_match = _area_matches_revenda(context.requester.area)
    purpose_match = _purpose_matches_material_request(context.purpose)
    area_reason = AREA_MATCH_REVENDA if area_match else AREA_OUTSIDE_REVENDA
    purpose_reason = PURPOSE_MATCH_MATERIAL_REQUEST if purpose_match else PURPOSE_NOT_CONFIRMED
    level: Literal["HIGH", "LOW"] = "HIGH" if area_match and purpose_match else "LOW"
    return ConfidenceAssessment(level, (area_reason, purpose_reason))
