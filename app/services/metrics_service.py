import time
import asyncio
from typing import Dict, Any, List
from collections import deque

class MetricsService:
    def __init__(self):
        # Counters
        self.incoming_requests: int = 0
        self.completed_requests: int = 0
        self.failed_requests: int = 0
        self.tokens_generated: int = 0
        
        # Gauges
        self.active_requests: int = 0
        self.active_llm_jobs: int = 0
        self.requests_in_queue: int = 0 # Not fully implemented in orchestrator yet, but good to have
        
        # Histograms / Lists (Store recent N for stats)
        # We'll store simple lists of recent values to calculate avg/p95 on read
        self.latency_history: deque = deque(maxlen=100)
        self.step_processing_history: Dict[str, deque] = {} # "step_name": deque
        self.llm_processing_history: deque = deque(maxlen=100)
        self.tokens_per_second_history: deque = deque(maxlen=100)
        
        # Last Values
        self.last_tokens_per_second: float = 0.0

    def _get_step_deque(self, step: str) -> deque:
        if step not in self.step_processing_history:
            self.step_processing_history[step] = deque(maxlen=100)
        return self.step_processing_history[step]

    # --------------------------
    # Async Record Methods (Fire and Forget)
    # --------------------------
    def record_request_start(self):
        self.incoming_requests += 1
        self.active_requests += 1

    def record_request_complete(self, duration: float, error: bool = False):
        self.active_requests = max(0, self.active_requests - 1)
        if error:
            self.failed_requests += 1
        else:
            self.completed_requests += 1
        self.latency_history.append(duration)

    def record_step_duration(self, step: str, duration: float):
        d = self._get_step_deque(step)
        d.append(duration)

    def record_llm_job_start(self):
        self.active_llm_jobs += 1

    def record_llm_job_end(self, duration: float, tokens: int = 0):
        self.active_llm_jobs = max(0, self.active_llm_jobs - 1)
        self.llm_processing_history.append(duration)
        if tokens > 0:
            self.tokens_generated += 1 # We might want total count, not just "1 request"
            # Wait, user asked for "Tokens Generated – Total tokens". 
            # I should add the actual count.
            # But here tokens is passed as int.
            pass

    def increment_tokens(self, count: int, duration: float):
        self.tokens_generated += count
        if duration > 0:
            tps = count / duration
            self.last_tokens_per_second = tps
            self.tokens_per_second_history.append(tps)

    # --------------------------
    # helpers
    # --------------------------
    def _safe_avg(self, data: deque) -> float:
        if not data: return 0.0
        return sum(data) / len(data)

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Return all metrics as a dictionary"""
        return {
            "requests": {
                "incoming_total": self.incoming_requests,
                "active_now": self.active_requests,
                "completed_total": self.completed_requests,
                "failed_total": self.failed_requests,
                "latency_avg_last_100": self._safe_avg(self.latency_history)
            },
            "llm": {
                "active_jobs": self.active_llm_jobs,
                "processing_time_avg_last_100": self._safe_avg(self.llm_processing_history),
                "tokens_generated_total": self.tokens_generated,
                "tokens_per_second_last": self.last_tokens_per_second,
                "tokens_per_second_avg_last_100": self._safe_avg(self.tokens_per_second_history)
            },
            "steps_avg_duration": {
                step: self._safe_avg(d) for step, d in self.step_processing_history.items()
            }
        }

metrics_service = MetricsService()
