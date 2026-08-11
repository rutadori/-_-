# ========================================================================================
# 
#   gui_app.py와 상호작용 하지 않은 코드입니다(삭제가능).
# 
# [모듈 이름] ai_connector.py (또는 extractor.py)
# [모듈 역할] 파일(TXT, PDF)에서 텍스트 콘텐츠를 추출하고, 로컬 AI 모델(Ollama)을 호출하여 태그/카테고리를 생성
#
# [이 모듈이 존재하는 이유]
# 1. 문서 읽기 자동화 (Text Extraction):
#    사용자가 수동으로 파일 내용을 열어보지 않아도, 파이썬 코드(pypdf 등)가 파일 내부 문자열을 읽어옵니다.
# 2. 오프라인 AI 연동 (Local LLM):
#    외부 API 키(OpenAI 등)나 인터넷 연결 없이, 로컬 PC에서 동작하는 Ollama(Qwen2.5 등)를 사용해
#    문서를 분석하므로 보안성이 높고 비용이 발생하지 않습니다.
# 3. 프롬프트 엔지니어링 표준화:
#    AI에게 원하는 형식('#태그1, #태그2')으로 답을 얻어내도록 프롬프트를 일관되게 구성하여 반환합니다.
# ========================================================================================

import os
import ollama
from pypdf import PdfReader


# ========================================================================================
# 1. 파일 확장자에 따른 텍스트 추출 함수
# ========================================================================================
def extract_text(file_path: str):
    """
    [파일 텍스트 추출 함수]

    ■ 매개변수:
        file_path (str): 읽어올 파일의 Absolute Path (절대 경로)

    ■ 반환값:
        str: 추출된 전체 텍스트 내용 (지원하지 않는 확장자일 경우 None)
    """
    # 텍스트(.txt) 파일인 경우 utf-8 인코딩으로 열어서 읽음
    if file_path.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    # PDF(.pdf) 파일인 경우 pypdf 라이브러리를 사용하여 페이지별 텍스트를 결합
    elif file_path.endswith('.pdf'):
        reader = PdfReader(file_path)
        text = ""
        # PDF 내부의 모든 페이지를 순회하며 텍스트를 가공 및 합침
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    # TXT, PDF 외의 지원하지 않는 파일 형식인 경우 None 반환
    return None


# ========================================================================================
# 2. 로컬 LLM(Ollama)에게 태그 추출 요청 함수
# ========================================================================================
def generate_tags(content: str):
    """
    [AI 핵심 태그 추출 함수]

    ■ 매개변수:
        content (str): 파일에서 추출한 텍스트 원문

    ■ 반환값:
        str: AI가 생성한 태그 문자열 (예: "#개발, #파이썬, #데이터베이스")
    """
    # 프롬프트 구성 (LLM에게 지시할 내용 정의)
    prompt = f"""
다음 문서를 읽고, 가장 중요한 핵심 키워드/태그를 3~5개 추출해라.
결과는 오직 '#태그1, #태그2, #태그3' 형태로만 출력해라.

[문서 내용]
{content[:2000]}  # LLM의 컨텍스트(토큰) 길이를 초과하지 않도록 상위 2000자만 잘라내어 입력
"""

    # Ollama API를 사용하여 실행 중인 로컬 LLM 모델(qwen2.5:3b)에 메시지 전달
    response = ollama.chat(
        model='qwen2.5:3b',  # 사용자의 PC에 Ollama로 다운로드되어 있어야 하는 모델명
        messages=[
            {'role': 'user', 'content': prompt}
        ]
    )

    # 응답 결과 중 모델이 생성한 메시지 텍스트 반환
    return response['message']['content']


# ========================================================================================
# 3. 단독 테스트 실행 블록 (모듈 동작 검증용)
# ========================================================================================
if __name__ == "__main__":
    print("🧪 [ai_connector.py] AI 분석 및 텍스트 추출 단독 테스트 시작...\n")

    # 분석을 진행할 샘플 파일 경로 설정
    file_target = "c:/python/sample.pdf"

    # 파일 존재 여부 확인 후 테스트 실행
    if os.path.exists(file_target):
        print(f"📄 대상 파일: {file_target}")
        extracted_text = extract_text(file_target)

        if extracted_text:
            print("✅ 텍스트 추출 성공! 로컬 AI(Ollama) 분석 요청 중...")
            ai_tags = generate_tags(extracted_text)
            print("\n🏷️ [AI 추출 태그 결과]")
            print(ai_tags)
        else:
            print("⚠️ 텍스트를 추출할 수 없거나 지원하지 않는 파일 형식입니다.")
    else:
        print(f"❌ 지정한 파일 경로가 존재하지 않습니다: {file_target}")