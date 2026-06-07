"""Clean minimal test."""
import pytest
from ai_capability_shelf.models import CapabilityShelfState

class TestCleanBasics:
    def test_import_ok(self):
        assert True

    def test_model_basics(self):
        s = CapabilityShelfState()
        assert s.atomic_components == {}
