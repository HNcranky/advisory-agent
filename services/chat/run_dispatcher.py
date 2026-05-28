from concurrent.futures import ThreadPoolExecutor

from services.chat.advisory_runner import run_advisory_for_session
from services.chat.repository import ChatSessionRepository

class RunDispatcher:
    def __init__(self, repository = None, runner = None, executor = None):
        self.repository = repository or ChatSessionRepository()
        self.runner = runner or run_advisory_for_session
        self.executor = executor or ThreadPoolExecutor(max_workers=2)
        
    def submit(self, session_token: str, run_id: int, latest_user_message: str, profile_state):
        self.executor.submit(
            self._execute,
            session_token,
            run_id,
            latest_user_message,
            profile_state
        )
        
    def _execute(self, session_token: str, run_id: int, latest_user_message: str, profile_state):
        self.repository.mark_run_running(run_id)
        try:
            result = self.runner(profile_state, latest_user_message, trace_run_id=run_id)
            final_answer = result.get("final_answer") or result.get("advisory") or ""
            self.repository.complete_run(run_id, result, final_answer)
            self.repository.append_message(session_token, "assistant", final_answer, "assistant_result")
            self.repository.update_session_status(session_token, "completed")
        except Exception as exc:
            self.repository.append_message(
                session_token,
                "assistant",
                "Xin loi, qua trinh phan tich bi gian doan. Ban hay thu lai.",
                "assistant_error",
            )
            self.repository.update_session_status(session_token, "failed")
            raise exc
                    