# ========================================================================================
# 
#   gui_app.py와 상호작용 하지 않은 코드입니다(삭제가능).
# 
# [모듈 이름] database.py
# [모듈 역할] SQLite 데이터베이스(file_manager.db) 파일과 연결하여 데이터의 저장/수정/조회/검색 전담
#
# [이 모듈이 존재하는 이유]
# 1. 영속성(Persistence) 유지:
#    프로그램이나 컴퓨터를 껐다 켜도 AI 분석 결과와 스캔한 파일 정보가 사라지지 않고 저장되도록 합니다.
# 2. 역할 분리 및 보안:
#    SQL 쿼리문(CREATE, INSERT, SELECT 등)을 한곳에 모아 관리함으로써
#    다른 모듈(service.py, main.py)이 SQL 문법을 몰라도 데이터베이스를 손쉽게 이용할 수 있게 합니다.
# 3. 데이터 중복 방지 (UPSERT):
#    이미 저장된 파일이 다시 스캔되었을 때 중복 저장되지 않고 기존 데이터의 AI 분석 결과만 갱신합니다.
# ========================================================================================

import sqlite3


class DatabaseManager:
    """
    [데이터베이스 관리 클래스]

    ■ 역할:
      SQLite DB 생성, 테이블 초기화, 파일 메타데이터 및 AI 분석 결과 저장/업데이트/조회/검색을 총괄합니다.
    """

    def __init__(self, db_name="file_manager.db"):
        """
        [생성자 함수]
        DatabaseManager 객체가 메모리에 만들어질 때 DB 파일명을 설정하고,
        테이블이 없으면 자동으로 생성(init_db)합니다.
        """
        # 생성할 SQLite 파일 이름을 변수에 저장합니다.
        self.db_name = db_name

        # 객체 생성 시점에 바로 테이블이 준비되도록 초기화 메서드를 호출합니다.
        self.init_db()

    def get_connection(self):
        """
        [DB 연결 객체 반환 함수]

        ■ 설명:
          SQLite 데이터베이스 파일과의 통신 통로(Connection)를 열어 반환합니다.
          Python의 'with' 구문과 함께 사용하면 작업 완료 후 자동으로 커넥션이 닫혀 메모리 누수를 방지합니다.
        """
        return sqlite3.connect(self.db_name)

    def init_db(self):
        """
        [테이블 초기화 함수]

        ■ 설명:
          데이터베이스 내에 데이터를 담을 'file_records' 테이블이 없으면 새로 생성합니다.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()  # DB 명령어를 실행하기 위한 일꾼(Cursor) 객체 생성

            # 테이블 생성 SQL 쿼리 실행 (IF NOT EXISTS: 기존 테이블이 없을 때만 생성)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 데이터 고유 번호 (1부터 자동 증가)
                    file_name TEXT NOT NULL,              -- 파일 이름 (필수 입력 항목)
                    file_path TEXT NOT NULL UNIQUE,       -- 파일 절대 경로 (중복 입력 불가 설정: UNIQUE)
                    file_size INTEGER,                    -- 파일 크기 (바이트 단위)
                    extension TEXT,                       -- 파일 확장자 (예: .py, .pdf)
                    ai_category TEXT,                     -- AI가 분류한 카테고리 (예: 소스 코드)
                    ai_tags TEXT,                         -- AI가 추천한 태그 (예: #python #sqlite)
                    ai_comment TEXT,                      -- AI 분석 코멘트
                    created_at TEXT,                      -- 파일 실제 생성 일시
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- DB 저장/분석 시각 (기본값: 현재시각)
                )
            """)
            conn.commit()  # 쿼리 실행 결과를 데이터베이스에 최종 반영(저장)합니다.

    def save_file_analysis(self, file_data: dict, ai_comment: str, ai_category: str, ai_tags: str = ""):
        """
        [파일 정보 및 AI 분석 데이터 저장/업데이트 함수 (UPSERT)]

        ■ 매개변수:
            file_data (dict): scanner.py에서 수집한 파일 정보 (file_name, file_path 등)
            ai_comment (str): AI가 작성한 문서 코멘트
            ai_category (str): AI가 분류한 카테고리
            ai_tags (str): AI가 추천한 태그 문자열
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # ON CONFLICT(file_path) DO UPDATE SET: SQLite의 UPSERT(Insert or Update) 기능
            # 만약 저장하려는 file_path가 이미 DB에 존재하면(중복 에러가 나면)
            # 신규 삽입 대신 기존 행의 ai_category, ai_tags, ai_comment, analyzed_at 값만 갱신합니다.
            cursor.execute("""
                INSERT INTO file_records (file_name, file_path, file_size, extension, ai_category, ai_tags, ai_comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    ai_category = excluded.ai_category,
                    ai_tags = excluded.ai_tags,
                    ai_comment = excluded.ai_comment,
                    analyzed_at = CURRENT_TIMESTAMP
            """, (
                file_data["file_name"],
                file_data["file_path"],
                file_data["file_size"],
                file_data["extension"],
                ai_category,
                ai_tags,
                ai_comment,
                file_data["created_at"]
            ))
            conn.commit()  # 데이터 저장 및 수정 내역 최종 반영

    def get_all_files(self):
        """
        [전체 데이터 조회 함수]

        ■ 설명:
          DB에 저장된 모든 파일의 메타데이터와 AI 분석 결과를 가져와 튜플 리스트로 반환합니다.
          GUI(main.py)의 화면 표(Table)에 데이터를 그릴 때 사용됩니다.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # ID, 파일명, 경로, 카테고리, 태그, 코멘트 컬럼 순서대로 전체 행 조회
            cursor.execute("SELECT id, file_name, file_path, ai_category, ai_tags, ai_comment FROM file_records")
            return cursor.fetchall()  # 조회된 모든 결과 데이터 행(Row)들을 반환 (튜플 리스트)

    def search_files(self, keyword: str):
        """
        [키워드 통합 검색 함수]

        ■ 매개변수:
            keyword (str): 사용자가 검색창에 입력한 검색어

        ■ 설명:
          검색어가 파일명, 카테고리, 태그, 코멘트 중 하나에라도 포함되어 있으면 가져옵니다.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # LIKE 구문 검색을 위해 검색어 양옆에 와일드카드 문자(%)를 추가 (예: '%python%')
            query = "%" + keyword + "%"

            # WHERE 절에서 OR 조건을 써서 4개 컬럼 중 하나라도 입력어가 맞물리면 추출합니다.
            cursor.execute("""
                SELECT id, file_name, file_path, ai_category, ai_tags, ai_comment 
                FROM file_records 
                WHERE file_name LIKE ? OR ai_category LIKE ? OR ai_tags LIKE ? OR ai_comment LIKE ?
            """, (query, query, query, query))

            return cursor.fetchall()  # 검색 조건에 맞아 떨어진 데이터 행들을 반환


# =========================================================
# [단독 테스트 실행 블록]
# =========================================================
# 이 파일(database.py)을 단독으로 실행하여 DB 동작을 검증할 때 쓰입니다.
if __name__ == "__main__":
    print("🧪 [database.py] 데이터베이스 모듈 단독 기능 테스트 시작...\n")

    # 1. 테스트용 전용 DB 파일 생성 및 연결
    db = DatabaseManager("test_file_manager.db")
    print("✅ 테스트용 DB 생성 및 초기화 완료!")

    # 2. 테스트용 샘플 데이터 준비
    sample_file = {
        "file_name": "db_test.py",
        "file_path": r"C:\projectTestFile\db_test.py",
        "file_size": 1024,
        "extension": ".py",
        "created_at": "2026-08-09 10:00:00"
    }

    # 3. 데이터 저장 기능 테스트
    db.save_file_analysis(
        file_data=sample_file,
        ai_comment="데이터베이스 제어용 파이썬 스크립트 파일입니다.",
        ai_category="소스 코드",
        ai_tags="#python #sqlite #database"
    )
    print("✅ 샘플 데이터 저장 성공!")

    # 4. 전체 데이터 조회 기능 테스트
    all_files = db.get_all_files()
    print(f"\n📂 [전체 파일 목록] (총 {len(all_files)}개)")
    for record in all_files:
        print(f"  • {record}")

    # 5. 키워드 검색 기능 테스트
    search_result = db.search_files("sqlite")
    print(f"\n🔍 ['sqlite' 키워드 검색 결과] (총 {len(search_result)}개)")
    for record in search_result:
        print(f"  • {record}")