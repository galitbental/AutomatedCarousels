"""Background tasks and the activity log shown in the UI."""
from __future__ import annotations

import itertools
import threading
import time
import traceback
from collections import deque
from datetime import datetime
from typing import Callable


class ActivityLog:
    def __init__(self, maxlen: int = 2000, echo: bool = True):
        self._items: deque = deque(maxlen=maxlen)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self.echo = echo

    def add(self, msg: str, level: str = "info", sku: str = "") -> None:
        entry = {"id": next(self._ids), "ts": datetime.now().strftime("%H:%M:%S"), "level": level,
                 "sku": sku, "msg": msg}
        with self._lock:
            self._items.append(entry)
        if self.echo:
            print(f"[{entry['ts']}] {level.upper():5} {sku + ': ' if sku else ''}{msg}", flush=True)

    def since(self, after: int = 0) -> list[dict]:
        with self._lock:
            return [e for e in self._items if e["id"] > after]


class Task:
    def __init__(self, tid: str, kind: str, sku: str, label: str, log: ActivityLog):
        self.id, self.kind, self.sku, self.label = tid, kind, sku, label
        self.status = "running"
        self.result = None
        self.error = ""
        self.started = time.time()
        self.finished: float | None = None
        self.cancel = threading.Event()
        self.messages: list[str] = []
        self._log = log

    def log(self, msg: str) -> None:
        self.messages.append(msg)
        self._log.add(msg, sku=self.sku)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "sku": self.sku, "label": self.label, "status": self.status,
                "error": self.error, "result": self.result, "messages": self.messages[-20:],
                "elapsed": round((self.finished or time.time()) - self.started, 1)}


class TaskManager:
    def __init__(self, log: ActivityLog):
        self.log = log
        self.tasks: dict[str, Task] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def start(self, kind: str, sku: str, label: str, fn: Callable[[Task], object]) -> Task:
        with self._lock:
            for t in self.tasks.values():
                if t.status == "running" and t.sku == sku and t.kind == kind:
                    return t  # same work already running
            task = Task(f"t{next(self._ids)}", kind, sku, label, self.log)
            self.tasks[task.id] = task
        self.log.add(f"Started: {label}", sku=sku)

        def run():
            try:
                task.result = fn(task)
                task.status = "cancelled" if task.cancel.is_set() else "done"
                self.log.add(f"Finished: {label}", sku=sku)
            except Exception as e:  # surfaced to the UI
                task.status = "cancelled" if task.cancel.is_set() else "error"
                task.error = str(e) or e.__class__.__name__
                level = "warn" if task.status == "cancelled" else "error"
                self.log.add(f"{'Cancelled' if level == 'warn' else 'Failed'}: {label}: {task.error}", level, sku)
                if level == "error" and not hasattr(e, "status"):
                    traceback.print_exc()
            finally:
                task.finished = time.time()

        threading.Thread(target=run, daemon=True).start()
        return task

    def get(self, tid: str) -> Task | None:
        return self.tasks.get(tid)

    def running(self) -> list[dict]:
        return [t.to_dict() for t in self.tasks.values() if t.status == "running"]

    def wait(self, tid: str, timeout: float = 60) -> Task:
        """Test helper: block until a task ends."""
        end = time.time() + timeout
        t = self.tasks[tid]
        while t.status == "running" and time.time() < end:
            time.sleep(0.05)
        return t
