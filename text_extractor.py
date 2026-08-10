# ========================================================================================
# [모듈 이름] text_extractor.py
# [모듈 역할] 지정된 경로의 파일 확장자를 판별하여 본문 텍스트를 안전하게 읽어오는 전처리 모듈
#
# [이 모듈이 존재하는 이유]
# 1. AI 처리 비용 및 속도 최적화 (max_chars):
#    몇 백MB에 달하는 대용량 파일 전체를 LLM에 전달하면 프롬프트 토큰 초과 에러가 나거나
#    응답 시간이 매우 길어집니다. 이를 방지하기 위해 앞부분 일정 글자(기본 1000자)만 잘라서 읽습니다.
# 2. 예외 처리 및 프로그램 안정성 확보:
#    인코딩이 깨지거나(UTF-8 미지원), 읽기 권한이 없거나, 이미와 같은 이진(Binary) 파일일 때
#    프로그램이 강제 종료(Crash)되지 않도록 예외 문구로 전환해줍니다.
# 3. 확장자별 분기 처리 일원화:
#    .txt, .md, .py 뿐만 아니라 이미지(.png, .jpg)나 바이너리(.exe, .zip) 파일을 사전 구분하여
#    각 포맷에 맞는 후속 작업(OCR, 예외 처리 등)을 원활하게 이어지도록 합니다.
# ========================================================================================

import os  # 파일 경로 탐색 및 확장자 분리를 위한 파이썬 표준 라이브러리


def extract_text_from_file(file_path: str, max_chars: int = 1000) -> str:
    """
    [파일 본문 텍스트 추출 함수]

    ■ 매개변수:
        file_path (str): 본문 글자를 읽어올 대상 파일의 전체 경로 (Absolute or Relative Path)
        max_chars (int): AI 프롬프트 용량 과부하 방지를 위한 최대 읽기 글자 수 (기본값: 1000자)

    ■ 반환값:
        str: 추출된 파일 본문 텍스트 (또는 파일 유형에 따른 안내/에러 문구)
    """
    # os.path.splitext(): 경로에서 ("파일명", ".확장자") 형태의 튜플로 분리합니다.
    # .lower(): 대소문자 차이로 인한 확장자 인식 오류를 방지하기 위해 소문자로 통일합니다. (예: ".TXT" -> ".txt")
    ext = os.path.splitext(file_path)[1].lower()

    # ---------------------------------------------------------
    # 1. 일반 텍스트 기반 파일 (.txt, .md, .py, .json, .csv, .log)
    # ---------------------------------------------------------
    if ext in ['.txt', '.md', '.py', '.json', '.csv', '.log']:
        try:
            # open(): 파일을 텍스트 읽기 모드('r')로 오픈
            # - encoding='utf-8': 한글 및 멀티바이트 문자 깨짐 방지
            # - errors='ignore': UTF-8로 해석 불가능한 문자가 포함되어 있어도 오류를 발생시키지 않고 무시
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # f.read(max_chars): 파일 전체 대신 지정한 글자 수(max_chars)만큼만 슬라이싱하여 추출
                content = f.read(max_chars)
                return content

        except Exception as e:
            # 파일 접근 권한 부족(PermissionError), 파일 손상 등의 예외 발생 시 에러 메시지 반환
            return f"[텍스트 읽기 오류: {e}]"

    # ---------------------------------------------------------
    # 2. 이미지 파일 (.jpg, .jpeg, .png, .bmp)
    # ---------------------------------------------------------
    elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        # 일반 텍스트로 읽을 경우 깨진 문자열이 들어가므로
        # 비전 AI 모델 또는 OCR 엔진 연동을 위한 식별용 안내 문자열 반환
        return "[이미지 파일: OCR 및 시각 모델 분석 필요]"

    # ---------------------------------------------------------
    # 3. 기타 이진(Binary) 파일 (.exe, .zip, .pdf 등)
    # ---------------------------------------------------------
    else:
        # 지원하지 않거나 바이너리 형태인 파일 처리
        return "[이진 또는 미지원 파일 형식]"


# =========================================================
# 단독 테스트 실행 블록 (모듈 검증용)
# =========================================================
if __name__ == "__main__":
    print("🧪 [text_extractor.py] 파일 본문 추출 모듈 단독 테스트 시작...\n")

    # 1. 테스트에 사용할 가상의 임시 텍스트 파일 이름
    sample_text_file = "test_sample.txt"

    # 2. 테스트용 임시 텍스트 파일 생성
    with open(sample_text_file, "w", encoding="utf-8") as f:
        f.write("안녕하세요! 이 파일은 text_extractor 모듈 기능 검증용 텍스트입니다.\n" * 10)

    # 3. 텍스트 파일 추출 테스트
    print("🔍 [1. 텍스트 파일 추출 테스트]")
    text_result = extract_text_from_file(sample_text_file, max_chars=60)
    print(f"결과:\n{text_result}\n")

    # 4. 이미지 파일 가상 테스트
    print("🔍 [2. 이미지 파일 가상 테스트]")
    img_result = extract_text_from_file("sample_photo.png")
    print(f"결과: {img_result}\n")

    # 5. 이진(Binary) 파일 가상 테스트
    print("🔍 [3. 미지원/바이너리 파일 테스트]")
    bin_result = extract_text_from_file("program.exe")
    print(f"결과: {bin_result}\n")

    # 6. 테스트 후 생성했던 임시 파일 깔끔하게 삭제
    if os.path.exists(sample_text_file):
        os.remove(sample_text_file)
        print("🧹 테스트 임시 파일 삭제 완료!")

""" 
f.read(max_chars): 
파일 크기가 몇 백 MB 이상으로 매우 클 때, 파일 전체를 읽어오면 메모리(RAM)가 부족해지거나 AI에게 너무 많은 데이터가 들어가 전송 오류가 날 수 있습니다. 
이를 방지하기 위해 앞부분 1000자만 안전하게 잘라서 가져오는 꿀팁 문법입니다.

errors='ignore': 
한글 파일에서 인코딩 방식(UTF-8, CP949 등) 차이로 인해 발생할 수 있는 UnicodeDecodeError를 무시하고 읽을 수 있는 부분까지 안전하게 추출해 줍니다.

os.path.splitext(path): 
파일 확장자를 다룰 때 필수적인 파이썬 표준 라이브러리 함수입니다.
"""