"""
STEP 5a TESTS — Check Library Loader
TDD: Tests written before implementation.
Run: uv run pytest tests/test_check_library.py -v
"""

import pytest
from services.check_library import (
    load_library,
    resolve_library,
    CheckLibrary,
    Check,
    CheckType,
)


# ── load_library ──────────────────────────────────────────────────────────────

def test_load_broadband_library_returns_check_library():
    lib = load_library("broadband-v1")
    assert isinstance(lib, CheckLibrary)


def test_load_broadband_library_has_correct_id():
    lib = load_library("broadband-v1")
    assert lib.id == "broadband-v1"
    assert lib.retailer_id == "retailer-broadband"


def test_load_broadband_library_has_checks():
    lib = load_library("broadband-v1")
    assert len(lib.checks) > 0


def test_load_energy_library_returns_check_library():
    lib = load_library("energy-v1")
    assert isinstance(lib, CheckLibrary)
    assert lib.retailer_id == "retailer-energy"


def test_load_unknown_library_raises_error():
    with pytest.raises(FileNotFoundError):
        load_library("does-not-exist-v1")


# ── Check fields ──────────────────────────────────────────────────────────────

def test_verbatim_checks_have_script_field():
    lib = load_library("broadband-v1")
    verbatim = [c for c in lib.checks if c.type == CheckType.VERBATIM]
    assert len(verbatim) > 0
    for check in verbatim:
        assert check.script is not None, f"{check.id} missing script"


def test_factual_checks_have_crm_field():
    lib = load_library("broadband-v1")
    factual = [c for c in lib.checks if c.type == CheckType.FACTUAL]
    assert len(factual) > 0
    for check in factual:
        assert check.crm_field is not None, f"{check.id} missing crm_field"


def test_critical_checks_block_sale():
    lib = load_library("broadband-v1")
    for check in lib.checks:
        if check.is_critical:
            assert check.blocks_sale, f"{check.id} is critical but does not block sale"


def test_behaviour_checks_do_not_block_sale():
    lib = load_library("broadband-v1")
    behaviour = [c for c in lib.checks if c.type == CheckType.BEHAVIOUR]
    for check in behaviour:
        assert not check.blocks_sale, f"{check.id} is BEHAVIOUR but blocks sale"


# ── resolve_library (version by retailer + date) ──────────────────────────────

def test_resolve_library_for_broadband_retailer():
    lib = resolve_library(retailer_id="retailer-broadband", call_date="2024-06-15")
    assert lib.retailer_id == "retailer-broadband"


def test_resolve_library_for_energy_retailer():
    lib = resolve_library(retailer_id="retailer-energy", call_date="2024-06-15")
    assert lib.retailer_id == "retailer-energy"


def test_resolve_library_returns_latest_effective_version():
    """Must return the most recent version effective on or before the call date."""
    lib = resolve_library(retailer_id="retailer-broadband", call_date="2025-01-01")
    assert lib.effective_from <= "2025-01-01"


def test_resolve_library_unknown_retailer_raises_error():
    with pytest.raises(ValueError, match="No check library found"):
        resolve_library(retailer_id="retailer-unknown", call_date="2024-06-15")


# ── Helper properties ─────────────────────────────────────────────────────────

def test_library_verbatim_checks_property():
    lib = load_library("broadband-v1")
    assert all(c.type == CheckType.VERBATIM for c in lib.verbatim_checks)


def test_library_factual_checks_property():
    lib = load_library("broadband-v1")
    assert all(c.type == CheckType.FACTUAL for c in lib.factual_checks)


def test_library_behaviour_checks_property():
    lib = load_library("broadband-v1")
    assert all(c.type == CheckType.BEHAVIOUR for c in lib.behaviour_checks)


def test_library_critical_checks_property():
    lib = load_library("broadband-v1")
    assert all(c.is_critical for c in lib.critical_checks)
