from concurrent.futures import ThreadPoolExecutor

from services.chat.compare_orchestrator import CompareOrchestrator
from services.chat.repository import ChatSessionRepository


class HybridDispatcher:
    def __init__(self, repository=None, orchestrator=None, executor=None):
        self.repository = repository or ChatSessionRepository()
        self.orchestrator = orchestrator or CompareOrchestrator()
        self.executor = executor or ThreadPoolExecutor(max_workers=2)

    def submit(self, session_token: str, run_id: int, content: str, profile_state, intent):
        self.executor.submit(self._execute, session_token, run_id, content, profile_state, intent)

    def _execute(self, session_token: str, run_id: int, content: str, profile_state, intent):
        self.repository.mark_run_running(run_id)
        try:
            answer = self.orchestrator.run(intent, profile_state, content, trace_run_id=run_id)
            self.repository.complete_run(run_id, {"final_answer": answer, "kind": "hybrid"}, answer)
            self.repository.append_message(session_token, "assistant", answer, "assistant_result")
            self.repository.update_session_status(session_token, "completed")
        except Exception as exc:
            self.repository.append_message(
                session_token,
                "assistant",
                "Xin loi, qua trinh tong hop bi gian doan. Ban hay thu lai.",
                "assistant_error",
            )
            self.repository.update_session_status(session_token, "failed")
            raise exc
