# ========================================================================================
# 
#   gui_app.py와 상호작용 하지 않은 코드입니다(삭제가능).
# 
# [모듈 이름] scanner.py
# [모듈 역할] 지정된 폴더 경로 내의 모든 파일을 찾아내고, 각 파일의 정보(메타데이터)를 수집
#
# [이 모듈이 존재하는 이유]
# 1. 역할 분리 (관심사의 분리):
#    GUI(main.py)나 서비스(service.py)에서 직접 파일 시스템을 다루면 코드가 매우 복잡해집니다.
#    "파일을 찾아오고 정보를 뽑아내는 일"만 전담하는 모듈을 따로 만들어 관리하기 위함입니다.
# 2. 재사용성:
#    단순히 폴더 경로 문자열 하나만 전달해주면, 복잡한 os 모듈 조작 없이
#    언제 어디서든 정제된 파일 정보 목록(리스트)을 얻을 수 있습니다.
# ========================================================================================

import os
from datetime import datetime


def scan_directory(dir_path: str) -> list[dict]:
    """
    [폴더 스캔 및 메타데이터 추출 핵심 함수]

    ■ 매개변수:
        dir_path (str): 파일 탐색을 시작할 폴더의 경로 (예: "C:/my_folder")

    ■ 반환값:
        list[dict]: 각 파일의 메타데이터가 담긴 딕셔너리들의 리스트
                    예: [{'file_name': 'test.txt', 'file_size': 1024, ...}, {...}]
    """

    # ---------------------------------------------------------
    # 1. 입력받은 폴더 경로가 컴퓨터에 실제로 존재하는지 예외 검사
    # ---------------------------------------------------------
    if not os.path.exists(dir_path):
        # 경로가 없는데 조회를 시작하면 에러가 나므로 미리 예외를 발생시키고 멈춥니다.
        raise FileNotFoundError(f"경로를 찾을 수 없습니다: {dir_path}")

    # 모든 파일의 정보 딕셔너리를 모아둘 빈 리스트 생성
    file_list = []

    # ---------------------------------------------------------
    # 2. os.walk()를 통한 하위 폴더 전체 재귀 탐색
    # ---------------------------------------------------------
    # os.walk()는 지정한 폴더부터 그 안의 모든 하위 폴더까지 싹 뒤져주는 파이썬 기본 함수입니다.
    # - root: 현재 탐색 중인 폴더의 경로 (문자열)
    # - _: 현재 폴더 안의 하위 폴더 이름 목록 (여기선 쓸 일이 없어 언더바 '_'로 처리)
    # - files: 현재 폴더 안에 들어있는 파일 이름 목록 (리스트)
    for root, _, files in os.walk(dir_path):
        for file in files:
            # os.path.join(): 운영체제(Windows, Mac)에 맞게 폴더 경로와 파일명을 안전하게 합쳐 전체 경로를 만듭니다.
            # 예: "C:\my_folder" + "test.txt" -> "C:\my_folder\test.txt"
            full_path = os.path.join(root, file)

            try:
                # os.stat(): 파일의 용량, 생성일, 수정일 등 운영체제가 관리하는 상세 상태 정보를 가져옵니다.
                stat = os.stat(full_path)

                # 파일의 핵심 메타데이터를 깔끔한 딕셔너리 형태(키-값 쌍)로 구조화합니다.
                file_info = {
                    # 1) 순수 파일 이름 (예: "report.pdf")
                    "file_name": file,
                    
                    # 2) 파일에 접근하기 위한 전체 절대 경로 (예: "C:/docs/report.pdf")
                    "file_path": full_path,
                    
                    # 3) 파일의 크기 (바이트 단위, Bytes)
                    "file_size": stat.st_size,
                    
                    # 4) 파일 확장자 추출 및 소문자 통일 (예: "REPORT.PDF" -> ".pdf")
                    "extension": os.path.splitext(file)[1].lower(),
                    
                    # 5) 생성 일시 (timestamp 숫자를 "YYYY-MM-DD HH:MM:SS" 날짜 문자열로 변환)
                    "created_at": datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    
                    # 6) 마지막 수정 일시 (timestamp 숫자를 날짜 문자열로 변환)
                    "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                }

                # 정제된 딕셔너리를 결과 리스트에 차곡차곡 담습니다.
                file_list.append(file_info)

            except Exception as e:
                # ---------------------------------------------------------
                # [방어적 코딩]
                # 파일 읽기 권한이 없거나 깨진 파일이 있더라도 전체 탐색 프로그램이 
                # 다운되지 않도록 예외(try-except) 처리로 감싸고 경고만 출력 후 다음 파일로 진행합니다.
                # ---------------------------------------------------------
                print(f"⚠️ 파일 읽기 오류 스킵 ({full_path}): {e}")

    # 탐색 및 메타데이터 수집이 완료된 최종 파일 리스트를 반환합니다.
    return file_list


# =========================================================
# [단독 테스트 실행 블록]
# =========================================================
# 이 파일(scanner.py)을 파이썬으로 직접 실행했을 때만 아래 테스트 코드가 구동됩니다.
# (main.py나 service.py에서 scanner 모듈을 가져다 쓸 때는 실행되지 않는 안전지대입니다.)
if __name__ == "__main__":
    print("🧪 [scanner.py] 모듈 단독 기능 테스트 시작...\n")

    # 컴퓨터 내에 실제 존재할 법한 테스트 경로 지정
    test_path = r"C:\projectTestFile2"

    try:
        print(f"🔍 '{test_path}' 폴더 스캔을 시작합니다...")
        results = scan_directory(test_path)

        print(f"\n✅ 스캔 완료! 총 {len(results)}개의 파일을 성공적으로 발견했습니다.\n")

        # 결과 리스트에서 상위 3개 파일 정보만 샘플로 출력
        print("--- [스캔 결과 샘플 3개 미리보기] ---")
        for info in results[:3]:
            print(f"• 파일명  : {info['file_name']}")
            print(f"  경로    : {info['file_path']}")
            print(f"  용량    : {info['file_size']} Bytes | 확장자: {info['extension']}")
            print(f"  생성일자: {info['created_at']} | 수정일자: {info['updated_at']}\n")

    except Exception as err:
        print(f"❌ 스캔 failure (에러 발생): {err}")