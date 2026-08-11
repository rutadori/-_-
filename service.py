# 
#   gui_app.py와 상호작용 하지 않은 코드입니다(삭제가능).
# 
# =========================================================
# [1] 백엔드 동작에 필요한 각 분야별 전용 모듈(파일) 임포트
# =========================================================
# scanner.py: 지정된 폴더 내부의 파일 메타데이터(파일명, 경로, 크기 등)를 수집하는 함수
from scanner import scan_directory

# database.py: SQLite 데이터베이스 생성, 저장, 업데이트를 전담 관리하는 클래스
from database import DatabaseManager

# ai_connector.py: 로컬 AI(Ollama) 또는 데이터 절약용 가짜 AI(Mock)와 통신하는 클래스
from ai_connector import LocalAIConnector

# text_extractor.py: PDF나 TXT 파일 등의 실제 본문 텍스트를 읽어오는 함수
from text_extractor import extract_text_from_file


# =========================================================
# [2] 백엔드 통합 관리 클래스 (BackendService)
# =========================================================
class BackendService:
    """
    [백엔드 중앙 통제실 (Orchestrator)]
    
    ■ 역할:
      GUI(main.py)가 DB, AI, 파일 스캔 모듈을 일일이 따로 다루지 않도록,
      '스캔 -> 텍스트 추출 -> AI 분석 -> DB 저장'이라는 백엔드의 모든 과정을 
      하나의 큰 흐름(파이프라인)으로 묶어서 총괄 제어하는 역할을 합니다.
    """

    def __init__(self):
        """
        [클래스 초기화 함수]
        BackendService 객체가 생성될 때 DB 제어기 및 AI 연동 객체를 사전에 준비합니다.
        """
        # DatabaseManager 객체를 메모리에 올려 DB 조작 준비를 마칩니다.
        self.db = DatabaseManager()

        # LocalAIConnector 객체를 만들되, use_mock=True 옵션을 주어 
        # API 사용량이나 AI 실행 부담을 줄이는 가짜(Mock) AI 모드로 동작하게 만듭니다.
        self.ai = LocalAIConnector(use_mock=True)

    def process_folder(self, folder_path: str):
        """
        [폴더 일괄 처리 메인 함수]
        
        main.py(GUI)에서 사용자가 폴더를 선택하고 버튼을 누르면 호출되는 함수입니다.
        전달받은 폴더 경로(folder_path) 내의 모든 파일을 순회하며 분석 및 저장을 진행합니다.
        """
        print(f"📂 '{folder_path}' 스캔 및 AI 분석 시작...")

        # ---------------------------------------------------------
        # Step 1. 지정된 폴더를 탐색하여 모든 파일의 메타데이터 수집
        # ---------------------------------------------------------
        # scanner 모듈을 실행해 파일 정보 딕셔너리들이 들어있는 리스트(files)를 얻습니다.
        files = scan_directory(folder_path)

        # ---------------------------------------------------------
        # Step 2. 수집된 파일들을 하나씩 순서대로 처리 (반복문)
        # ---------------------------------------------------------
        for file_info in files:

            # 2-1. 파일의 본문 텍스트 추출 (예: 최대 1000자까지 실제 문서 내용을 읽어옴)
            text_content = extract_text_from_file(file_info["file_path"])

            # 2-2. 수집한 메타데이터(file_info)와 본문(text_content)을 AI에게 전달하여 분석 진행
            ai_res = self.ai.analyze_file_with_metadata(file_info, text_content)

            # 2-3. AI 응답 데이터 중 태그(ai_tags)의 데이터 형태 안전하게 가공하기
            # (방어적 코딩: AI가 태그를 ['#개발', '#파이썬'] 형태의 리스트로 주면 "#개발, #파이썬" 형태의 문자열로 합쳐주고,
            #  이미 문자열이면 그대로 사용하며, 값이 없으면 빈 문자열("")을 넣습니다.)
            tags_str = (
                ", ".join(ai_res.get("ai_tags", []))
                if isinstance(ai_res.get("ai_tags"), list)
                else ai_res.get("ai_tags", "")
            )

            # 2-4. 최종 정리된 메타데이터 + AI 분석 결과를 SQLite DB에 저장 (동일한 파일은 자동 업데이트)
            self.db.save_file_analysis(
                file_data=file_info,
                ai_comment=ai_res.get("ai_comment", ""),
                ai_category=ai_res.get("ai_category", "기타"),
                ai_tags=tags_str
            )

        print("🎉 스캔, AI 분석, DB 저장까지 완벽 완료!")


# =========================================================
# [3] 백엔드 단독 테스트 실행 블록 (주요 개념 설명)
# =========================================================
# ※ 주의: 이 파일(service.py)은 백엔드 로직 전용 파일이므로 main.py를 대체할 수 없습니다!
#
# 아래의 `if __name__ == "__main__":` 조건문은
# 개발자가 main.py(GUI 화면)를 켜지 않고, 이 service.py 파일만 파이썬으로 '단독 실행'했을 때만 작동합니다.
# (main.py에서 service.py를 불러와서 사용할 때는 아래 코드가 실행되지 않고 무시됩니다.)

if __name__ == "__main__":
    print("⚠️ [개발자 단독 테스트 모드] service.py 파일만 직접 실행했습니다.")
    
    # 1. 백엔드 서비스 객체 생성
    service = BackendService()

    # 2. GUI 화면 대신 코드에 직접 적은 테스트 경로로 일괄 처리 함수 테스트
    service.process_folder(r"C:\projectTestFile2")


"""
========================================================================================
💡 구조 및 개념 요약 정리 (초보자 참고용)
========================================================================================

1. main.py 와 service.py 의 파일 관계:
   - main.py (프론트엔드/GUI):
     사용자 눈에 보이는 프로그램 창, 버튼, 파일 선택 창, 분석 결과표 화면을 제공합니다.
     사용자가 버튼을 클릭하면 service.py 의 process_folder() 함수를 불러와 동작시킵니다.
   - service.py (백엔드 엔진):
     눈에 보이는 화면은 없으며, 실제 파일 스캔, 텍스트 추출, AI 분석, DB 저장이라는 
     복잡한 내부 핵심 로직(Business Logic)을 구동합니다.

2. 중앙 통제 (Orchestration):
   - main.py 에서 DB, AI, Scanner 등을 일일이 컨트롤하면 코드가 비대해지고 얽힙니다.
   - BackendService 라는 하나의 대표 클래스만 만들어 두고, main.py 는 단 한 줄의 함수 호출
     `service.process_folder(경로)` 만 실행하도록 설계하여 코드를 깨끗하게 유지합니다.

3. 방어적 코딩 (isinstance 검사):
   - AI 가 돌려주는 결과값 중 태그(ai_tags)가 리스트일 수도 있고 단순 문자열일 수도 있습니다.
   - isinstance(..., list) 처리를 해둠으로써 예상치 못한 데이터 형태가 들어와 프로그램이 
     갑자기 강제 종료(다운)되는 사고를 방지합니다.
========================================================================================
"""