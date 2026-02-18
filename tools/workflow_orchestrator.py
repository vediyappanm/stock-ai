"""Workflow state tracking and strict 6-step execution enforcement."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable, Dict, MutableMapping

from config.settings import settings
from schemas.response_schemas import WorkflowStatus
from tools.error_handler import StockAnalystError, UnknownError, format_error_response


StepHandler = Callable[[MutableMapping[str, object]], None]


class WorkflowOrchestrator:
    """In-memory workflow lifecycle manager."""

    def __init__(self) -> None:
        self._store: Dict[str, WorkflowStatus] = {}
        self._lock = Lock()

    def _purge(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.workflow_retention_hours)
        stale = [wid for wid, item in self._store.items() if item.updated_at < cutoff]
        for wid in stale:
            self._store.pop(wid, None)

    def _progress(self, completed_count: int) -> float:
        return float((completed_count / settings.total_workflow_steps) * 100.0)

    def create_workflow(self) -> WorkflowStatus:
        with self._lock:
            self._purge()
            workflow_id = str(uuid.uuid4())
            status = WorkflowStatus(
                workflow_id=workflow_id,
                status="running",
                current_step=settings.workflow_steps[0],
                completed_steps=[],
                progress_percentage=0.0,
            )
            self._store[workflow_id] = status
            return status

    def get_workflow_status(self, workflow_id: str) -> WorkflowStatus | None:
        with self._lock:
            self._purge()
            return self._store.get(workflow_id)

    def execute_prediction_workflow(
        self,
        context: MutableMapping[str, object],
        handlers: Dict[str, StepHandler],
    ) -> tuple[str, MutableMapping[str, object]]:
        """
        Run handlers in strict configured step order and track status.
        """
        status = self.create_workflow()
        workflow_id = status.workflow_id
        completed: list[str] = []

        try:
            for step in settings.workflow_steps:
                if step not in handlers:
                    raise UnknownError(
                        f"Missing handler for workflow step '{step}'",
                        failed_step=step,
                        completed_steps=completed.copy(),
                    )

                with self._lock:
                    current = self._store[workflow_id]
                    current.current_step = step
                    current.updated_at = datetime.now(timezone.utc)
                    self._store[workflow_id] = current

                handlers[step](context)
                completed.append(step)

                with self._lock:
                    current = self._store[workflow_id]
                    current.completed_steps = completed.copy()
                    current.progress_percentage = self._progress(len(completed))
                    current.updated_at = datetime.now(timezone.utc)
                    self._store[workflow_id] = current

            with self._lock:
                current = self._store[workflow_id]
                current.status = "completed"
                current.current_step = None
                current.progress_percentage = 100.0
                current.updated_at = datetime.now(timezone.utc)
                self._store[workflow_id] = current

            return workflow_id, context

        except Exception as exc:
            wrapped = exc if isinstance(exc, StockAnalystError) else UnknownError(str(exc))
            error_response = format_error_response(
                wrapped,
                failed_step=getattr(wrapped, "failed_step", None),
                completed_steps=completed.copy(),
                workflow_id=workflow_id,
            )
            with self._lock:
                current = self._store[workflow_id]
                current.status = "failed"
                current.failed_step = error_response.failed_step
                current.error_message = error_response.error_message
                current.completed_steps = completed.copy()
                current.progress_percentage = self._progress(len(completed))
                current.updated_at = datetime.now(timezone.utc)
                self._store[workflow_id] = current
            raise


workflow_orchestrator = WorkflowOrchestrator()
