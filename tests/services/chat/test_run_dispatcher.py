from services.chat.models import ChatProfileState
from services.chat.run_dispatcher import RunDispatcher


class FakeRepository:
    def __init__(self):
        self.completed = None
        self.messages = []
        self.status = None

    def mark_run_running(self, run_id):
        self.status = ("running", run_id)

    def complete_run(self, run_id, result_json, final_answer):
        self.completed = (run_id, result_json, final_answer)

    def append_message(self, session_token, role, content, kind="chat"):
        self.messages.append((session_token, role, kind, content))

    def update_session_status(self, session_token, status):
        self.status = (status, session_token)


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


def test_dispatcher_completes_run_and_posts_result_message():
    repo = FakeRepository()
    dispatcher = RunDispatcher(
        repository=repo,
        runner=lambda profile_state, latest_user_message: {"final_answer": "De xuat phu hop"},
        executor=InlineExecutor(),
    )

    dispatcher.submit(
        session_token="session-123",
        run_id=7,
        latest_user_message="Em duoc 27 diem",
        profile_state=ChatProfileState(
            admission_year=2026,
            total_score=27.0,
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )

    assert repo.completed[0] == 7
    assert repo.completed[2] == "De xuat phu hop"
    assert repo.messages[-1][2] == "assistant_result"