from typing import Literal, Optional

from pydantic import BaseModel

from services import build_default_gateway
from services.chat.models import ChatProfileState
from services.inference.models import InferenceRequest

INTENT_SYSTEM_PROMPT = """
Bạn là bộ phân loại intent cho hệ thống tư vấn tuyển sinh đại học Việt Nam.

Phân loại tin nhắn của user vào đúng 1 trong 5 route:

ADVISORY_FLOW — câu hỏi tư vấn chọn ngành/trường dựa trên điểm số, nguyện vọng, khả năng đậu
  Ví dụ: "25 điểm A00 nên chọn trường nào", "em có đậu NEU không", "tư vấn ngành CNTT"

KNOWLEDGE_QA — câu hỏi thực tế về thông tin cụ thể của trường/ngành
  Ví dụ: "học phí UET bao nhiêu", "chương trình CNTT gồm gì", "có học bổng không", "ký túc xá thế nào"

CLARIFICATION — câu quá mơ hồ, thiếu context để phân loại chính xác
  Ví dụ: "thế còn cái đó thì sao" (không rõ đối tượng), "ý bạn là gì"

OUT_OF_SCOPE — hoàn toàn ngoài lĩnh vực tuyển sinh đại học
  Ví dụ: "thời tiết hôm nay", "kể chuyện cười", "1+1 bằng mấy", "giúp tôi viết code"

HYBRID — cần cả dữ liệu tư vấn (điểm chuẩn, xác suất đậu) lẫn thông tin thực tế (học phí, chương trình)
  Ví dụ: "so sánh UET và HUST về điểm chuẩn lẫn học phí"
  Chỉ dùng HYBRID khi câu hỏi thực sự cần cả hai loại dữ liệu.

Quy tắc resolve đại từ:
- "trường này", "ở đó", "trường đó" → dùng preferred_schools trong profile (nếu có)
- "ngành này", "chuyên ngành đó" → dùng preferred_majors trong profile (nếu có)
- Không thể resolve → để school/topic là null, route về CLARIFICATION

Chuẩn hóa tên trường thành viết tắt phổ biến nếu nhận ra: VNU-UET, HUST, NEU, VNU-HCMUS, UEH, FTU, ...

Trả về JSON hợp lệ, không giải thích thêm:
{"route": "...", "topic": "...", "school": "..."}
""".strip()


class IntentResult(BaseModel):
    route: Literal[
        "ADVISORY_FLOW", "KNOWLEDGE_QA", "HYBRID", "CLARIFICATION", "OUT_OF_SCOPE"
    ]
    topic: Optional[
        Literal[
            "tuition",
            "curriculum",
            "scholarship",
            "dormitory",
            "career",
            "admission_policy",
            "program_overview",
        ]
    ] = None
    school: Optional[str] = None


_FALLBACK = IntentResult(route="ADVISORY_FLOW")


class IntentRouter:
    def __init__(self, gateway=None):
        self._gateway = gateway or build_default_gateway()

    def classify(self, message: str, profile_state: ChatProfileState) -> IntentResult:
        try:
            if hasattr(self._gateway, "is_available") and not self._gateway.is_available():
                return _FALLBACK
            result = self._gateway.run(
                InferenceRequest(
                    agent_name="intent_router",
                    task_type="intent_classification",
                    system_prompt=INTENT_SYSTEM_PROMPT,
                    user_prompt=self._build_user_prompt(message, profile_state),
                    output_mode="json",
                    temperature=0.0,
                )
            )
            if not result.parsed_data:
                return _FALLBACK
            return IntentResult.model_validate(result.parsed_data)
        except Exception:
            return _FALLBACK

    def _build_user_prompt(self, message: str, profile_state: ChatProfileState) -> str:
        schools = (
            ", ".join(profile_state.preferred_schools)
            if profile_state.preferred_schools
            else "chưa có"
        )
        majors = (
            ", ".join(profile_state.preferred_majors)
            if profile_state.preferred_majors
            else "chưa có"
        )
        return (
            f'Tin nhắn: "{message}"\n\n'
            f"Profile hiện tại:\n"
            f"- Trường quan tâm: {schools}\n"
            f"- Ngành quan tâm: {majors}\n"
            f"- Điểm số: {profile_state.total_score or 'chưa có'}\n"
            f"- Khối thi: {profile_state.subject_combination or 'chưa có'}"
        )
