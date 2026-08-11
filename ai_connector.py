# ========================================================================================
# 
#   gui_app.py와 상호작용 하지 않은 코드입니다(삭제가능).
# 
# [모듈 이름] ai_connector.py
# [모듈 역할] 로컬 AI 엔진(Ollama)을 호출하여 파일 분석 결과를 정형화된 JSON 데이터로 파싱 및 반환
#
# [이 모듈이 존재하는 이유]
# 1. 텍스트 응답의 정형화 (JSON Output):
#    자연어로 응답하는 LLM의 특성상 화면에 그대로 출력하거나 DB에 저장하기 어렵습니다.
#    'format="json"' 옵션과 프롬프트 템플릿을 조합해 파이썬 딕셔너리(dict) 형태로 데이터 추출을 보장합니다.
# 2. 견고한 예외 처리 (Fallback System):
#    Ollama 서비스 미실행, 서버 메모리 부족, 모델 미다운로드 등 AI 구동 시 발생 가능한
#    런타임 오류가 발생해도 시스템 전체가 멈추지 않고 예외 메시지를 반환하도록 보호합니다.
# 3. 테스트 및 개발 용이성:
#    단독 테스트(if __name__ == "__main__") 구문을 내장하여 backend_service나 main.py 구동 없이도
#    로컬 LLM과의 통신 상태를 독립적으로 검증할 수 있습니다.
# ========================================================================================

import json   # AI가 반환한 JSON 텍스트 문자열을 파이썬 객체(dict)로 파싱하기 위한 라이브러리
import ollama # 컴퓨터에 설치된 로컬 Ollama AI 엔진과 통신하는 전용 라이브러리


class LocalAIConnector:
    """
    [로컬 AI 연동 클래스]
    
    ■ 역할:
      컴퓨터에 설치된 로컬 LLM(Ollama / Qwen2.5)을 호출하여 
      파일 내용 분석 결과를 규격화된 JSON 형식으로 받아옵니다.
    """
    def __init__(self, model_name="qwen2.5:3b", use_mock=False):
        """
        [생성자 함수]
        
        ■ 매개변수:
            model_name (str): Ollama에 로드할 로컬 모델명 (기본값: qwen2.5:3b)
            use_mock (bool): 테스트용 모의 데이터 사용 여부
        """
        self.model_name = model_name
        self.use_mock = use_mock

    def analyze_file_content(self, file_name: str, file_text: str) -> dict:
        """
        [파일 내용 분석 및 코멘트 생성 함수]

        ■ 매개변수:
            file_name (str): 분석할 파일의 이름 (예: projectTestFile1.txt)
            file_text (str): 추출된 파일의 텍스트 본문 내용

        ■ 반환값:
            dict: {"ai_category": "...", "ai_comment": "..."} 형태의 파이썬 딕셔너리
        """
        
        # ---------------------------------------------------------
        # 1. AI 모델에게 전달할 지시문(프롬프트) 작성
        # ---------------------------------------------------------
        # f-string을 활용하여 프롬프트 템플릿 내부에 파일명과 파일 본문을 동적으로 삽입합니다.
        prompt = f"""
너는 파일 분석 AI야. 아래 전달받은 파일 내용을 분석해서 **반드시 JSON 포맷**으로만 응답해 줘.

[파일 정보]
- 파일명: {file_name}
- 파일 내용:
{file_text}

[응답 형식 예시]
{{
  "ai_category": "문서 카테고리 (예: 테스트 문서, 보고서 등)",
  "ai_comment": "파일 내용을 요약하고 오타나 특이사항을 정리한 한 줄 코멘트"
}}
"""

        try:
            print(f"🤖 로컬 AI({self.model_name})에게 파일 분석 요청 중...")
            
            # ---------------------------------------------------------
            # 2. Ollama API 호출 (실제 로컬 AI 모델 구동)
            # ---------------------------------------------------------
            # - model: 사용할 AI 모델 지정
            # - messages: 사용자의 입력(prompt) 메시지 배열 전달
            # - format='json': AI 출력을 강제로 JSON 구조로 제한 (파싱 오류 방지)
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}],
                format='json'  # ✨ Qwen 모델에게 JSON 출력 강제 지정!
            )

            # ---------------------------------------------------------
            # 3. AI 응답 문자열을 파이썬 딕셔너리 객체로 변환
            # ---------------------------------------------------------
            # response['message']['content']에 담긴 JSON 텍스트 문자열을 dict 타입으로 변환합니다.
            result_json = json.loads(response['message']['content'])
            return result_json

        except Exception as e:
            # ---------------------------------------------------------
            # 4. 예외 처리 (Fallback Logic)
            # ---------------------------------------------------------
            # Ollama 서비스 미실행, 모델 미설치, 메모리 부족 등의 오류 발생 시 
            # 프로그램이 다운되지 않고 에러 정보를 담은 기본 딕셔너리를 반환합니다.
            print(f"❌ AI 연동 오류 발생: {e}")
            return {
                "ai_category": "분석 실패",
                "ai_comment": f"로컬 AI 연동 중 오류가 발생했습니다 ({e})"
            }


# =========================================================
# 단독 테스트 실행 블록 (모듈 검증용)
# =========================================================
if __name__ == "__main__":
    # LocalAIConnector 객체 생성 (기본값인 qwen2.5:3b 모델 호출)
    ai = LocalAIConnector()
    
    # AI 테스트용 샘플 텍스트 (영문 및 오타가 포함된 테스트 문구)
    sample_text = """
    This is Test Pile.
    AI can this pile?
    Please read me.
    and, this pile is saved to txt pile
    """
    
    # AI 커넥터 호출 및 분석 결과 받기
    res = ai.analyze_file_content("projectTestFile1.txt", sample_text)
    
    # 최종 결과 출력
    print("\n================ [ 진짜 로컬 AI 응답 결과 ] ================")
    print(f"카테고리: {res.get('ai_category')}")
    print(f"AI 코멘트: {res.get('ai_comment')}")
    print("==========================================================")