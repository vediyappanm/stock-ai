"""Property-based tests for core invariants."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from models.ensemble import combine_predictions
from tools.workflow_orchestrator import WorkflowOrchestrator


@settings(max_examples=100, deadline=None)
@given(
    rf=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    lstm=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_property_13_ensemble_weighting_formula(rf: float, lstm: float) -> None:
    combined = combine_predictions(rf_prediction=rf, lstm_prediction=lstm)
    expected = (0.6 * rf) + (0.4 * lstm)
    assert abs(combined - expected) < 1e-9


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=2, max_value=20))
def test_property_40_workflow_id_uniqueness(count: int) -> None:
    orchestrator = WorkflowOrchestrator()
    ids = [orchestrator.create_workflow().workflow_id for _ in range(count)]
    assert len(set(ids)) == len(ids)

