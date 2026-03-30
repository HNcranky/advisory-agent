# extractors/admission_extractor.py

import re
from models.admission_schema import AdmissionDocument, ProgramAdmission, AdmissionMethod


PROGRAM_PATTERNS = [

    # pattern: ngành (IT1) 300 chỉ tiêu
    r"([A-ZĐA-Za-zÀ-ỹ\s]+)\((.*?)\).*?(\d+)\s*chỉ tiêu",

    # pattern: ngành xxx mã xxx chỉ tiêu xxx
    r"Ngành\s*(.*?)\s*Mã\s*(.*?)\s*Chỉ tiêu\s*(\d+)",

    # pattern: ngành xxx tuyển xxx chỉ tiêu
    r"Ngành\s*(.*?)\s*tuyển\s*(\d+)\s*chỉ tiêu"

]


def detect_university(text):

    if "Bách Khoa" in text or "HUST" in text:
        return "Hanoi University of Science and Technology"

    if "Đại học Công nghệ" in text:
        return "VNU University of Engineering and Technology"

    return "Unknown University"


def extract_programs(text):

    programs = []

    for pattern in PROGRAM_PATTERNS:

        matches = re.findall(pattern, text, re.IGNORECASE)

        for m in matches:

            program_name = m[0].strip()

            quota = None
            for item in m:
                if item.isdigit():
                    quota = int(item)

            if not quota:
                continue

            method = AdmissionMethod(
                method_name="THPT",
                quota=quota
            )

            program = ProgramAdmission(
                university="Unknown",
                program_name=program_name,
                admission_methods=[method]
            )

            programs.append(program)

    return programs


def extract_admission(text: str, source_url: str):

    university = detect_university(text)

    programs = extract_programs(text)

    doc = AdmissionDocument(
        source_url=source_url,
        university=university,
        year=2025,
        programs=programs
    )

    return doc