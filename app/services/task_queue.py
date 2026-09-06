"""Async task queue for long-running operations like image generation."""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from queue import Queue
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Represents an async task."""
    task_id: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    user_id: Optional[int] = None
    dream_id: Optional[int] = None
    panel_number: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


class TaskQueue:
    """Simple in-memory async task queue with thread worker."""

    def __init__(self, num_workers: int = 1):
        """Initialize queue with worker threads."""
        self.queue: Queue = Queue()
        self.tasks: dict[str, Task] = {}
        self.workers_running = True
        self.lock = threading.Lock()
        self.app = None  # Flask app context for worker threads

        # Start worker threads
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i}",
                daemon=True,
            )
            worker.start()
            logger.info("Started task worker thread %s", worker.name)

    def submit(
        self,
        func: Callable,
        *args,
        user_id: Optional[int] = None,
        dream_id: Optional[int] = None,
        panel_number: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Submit a task to the queue.

        Args:
            func: Callable to execute
            *args: Positional arguments for func
            user_id: Optional user ID for context
            dream_id: Optional dream ID for context
            panel_number: Optional panel number for context
            **kwargs: Keyword arguments for func

        Returns:
            task_id: Unique task identifier
        """
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            user_id=user_id,
            dream_id=dream_id,
            panel_number=panel_number,
        )

        with self.lock:
            self.tasks[task_id] = task

        self.queue.put((task_id, func, args, kwargs))
        logger.info("Submitted task %s for dream %s panel %s", task_id, dream_id, panel_number)
        return task_id

    def set_app(self, app) -> None:
        """Set Flask app for worker thread context."""
        self.app = app

    def get_status(self, task_id: str) -> Optional[Task]:
        """Get task status by ID."""
        with self.lock:
            return self.tasks.get(task_id)

    def _worker_loop(self):
        """Worker thread main loop."""
        while self.workers_running:
            try:
                # Get next task from queue (timeout prevents blocking indefinitely)
                task_data = self.queue.get(timeout=1)
                if task_data is None:
                    continue

                task_id, func, args, kwargs = task_data

                with self.lock:
                    task = self.tasks.get(task_id)
                    if task:
                        task.status = TaskStatus.RUNNING
                        task.started_at = datetime.now(timezone.utc)
                        # Add metadata to kwargs so function has all required args
                        if task.user_id is not None:
                            kwargs['user_id'] = task.user_id
                        if task.dream_id is not None:
                            kwargs['dream_id'] = task.dream_id
                        if task.panel_number is not None:
                            kwargs['panel_number'] = task.panel_number

                try:
                    # Execute the function with Flask app context if available
                    if self.app:
                        with self.app.app_context():
                            result = func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                    with self.lock:
                        task = self.tasks.get(task_id)
                        if task:
                            task.status = TaskStatus.COMPLETED
                            task.result = result
                            task.completed_at = datetime.now(timezone.utc)
                    logger.info("Task %s completed successfully", task_id)

                except Exception as exc:  # noqa: BLE001
                    logger.exception("Task %s failed with error", task_id)
                    with self.lock:
                        task = self.tasks.get(task_id)
                        if task:
                            task.status = TaskStatus.FAILED
                            task.error = str(exc)
                            task.completed_at = datetime.now(timezone.utc)

                self.queue.task_done()

            except Exception:  # noqa: BLE001
                # Queue timeout is normal, other exceptions are logged
                pass

    def shutdown(self):
        """Gracefully shutdown worker threads."""
        self.workers_running = False
        logger.info("Task queue shutdown initiated")


# Global queue instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get or create the global task queue."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(num_workers=2)
    return _task_queue
