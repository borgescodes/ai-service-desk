from dataclasses import replace

import pytest

from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationError,
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryConfigurationError,
    TechnicianRegistryEntry,
)

TECH = TechnicianIdentity(
    "TECH-001", "synthetic.tech", "Synthetic Technician", "tech@example.invalid"
)
ENTRY = TechnicianRegistryEntry(TECH, frozenset({"CDM_ACCESS_REQUEST"}))


def expect_registry_error(entries, code):
    with pytest.raises(TechnicianRegistryConfigurationError) as exc:
        TechnicianAuthorizationRegistry(entries)
    assert exc.value.reason_code == code


@pytest.mark.parametrize(
    "entry",
    [
        None,
        {},
        replace(ENTRY, identity=None),
        replace(ENTRY, identity=replace(TECH, name="")),
        replace(ENTRY, capabilities="CDM_ACCESS_REQUEST"),
    ],
)
def test_registry_invalid_entry_fails_closed_before_indexing(entry):
    expect_registry_error([ENTRY, entry], "TECHNICIAN_REGISTRY_INVALID")


@pytest.mark.parametrize("capability", [None, 1, "", "ab", " lower ", [], "A" * 121])
def test_registry_invalid_capability_fails_closed(capability):
    expect_registry_error(
        [replace(ENTRY, capabilities=[capability])], "TECHNICIAN_REGISTRY_INVALID"
    )


@pytest.mark.parametrize(
    "capability",
    ["*", "CDM_*", "CDM_ACCESS", "CDM~ACCESS", "cdm_access_request", " CDM_ACCESS_REQUEST"],
)
def test_registry_rejects_wildcard_prefix_and_fuzzy_capabilities(capability):
    if capability == "CDM_ACCESS":
        registry = TechnicianAuthorizationRegistry(
            [replace(ENTRY, capabilities=frozenset({capability}))]
        )
        with pytest.raises(TechnicianAuthorizationError):
            registry.require_capability(TECH, "CDM_ACCESS_REQUEST")
    else:
        expect_registry_error(
            [replace(ENTRY, capabilities=frozenset({capability}))], "TECHNICIAN_REGISTRY_INVALID"
        )


def conflict(field):
    other = TechnicianIdentity(
        "TECH-002", "second.tech", "Other Technician", "other@example.invalid"
    )
    other = replace(other, **{field: " " + getattr(TECH, field).upper() + " "})
    expect_registry_error(
        [ENTRY, TechnicianRegistryEntry(other, frozenset())], "TECHNICIAN_REGISTRY_CONFLICT"
    )


def test_registry_rejects_normalized_technician_id_conflict():
    conflict("technician_id")


def test_registry_rejects_normalized_username_conflict():
    conflict("username")


def test_registry_rejects_normalized_email_conflict():
    conflict("email")


def test_registry_invalid_entry_precedes_potential_conflict():
    expect_registry_error([ENTRY, ENTRY, None], "TECHNICIAN_REGISTRY_INVALID")


def test_registry_authorizes_exact_capability_and_identity():
    registry = TechnicianAuthorizationRegistry([ENTRY])
    assert registry.require_capability(TECH, "CDM_ACCESS_REQUEST") is None


@pytest.mark.parametrize(
    "technician,capability",
    [
        (replace(TECH, email="wrong@example.invalid"), "CDM_ACCESS_REQUEST"),
        (replace(TECH, technician_id="missing"), "CDM_ACCESS_REQUEST"),
        (TECH, "CDM_ACCESS_REQUEST_MORE"),
        (TECH, "*"),
        (TECH, []),
        (None, "CDM_ACCESS_REQUEST"),
    ],
)
def test_registry_denies_identity_mismatch_and_nonexact_capability(technician, capability):
    registry = TechnicianAuthorizationRegistry([ENTRY])
    with pytest.raises(TechnicianAuthorizationError) as exc:
        registry.require_capability(technician, capability)
    assert exc.value.reason_code == "TECHNICIAN_CAPABILITY_REQUIRED"


def test_registry_freezes_caller_capability_collection():
    capabilities = {"CDM_ACCESS_REQUEST"}
    registry = TechnicianAuthorizationRegistry([TechnicianRegistryEntry(TECH, capabilities)])
    capabilities.add("OTHER_CAPABILITY")
    with pytest.raises(TechnicianAuthorizationError):
        registry.require_capability(TECH, "OTHER_CAPABILITY")
