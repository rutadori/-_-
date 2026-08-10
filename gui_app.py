# =========================================================
# [1] 파이썬 기본 표준 라이브러리 불러오기 (Import)
# =========================================================
import sys        # 파이썬 시스템 및 명령줄 인자 관리 (프로그램 종료 시 필요)
import os         # 파일 경로 접근, 폴더 탐색, 파일 메타데이터(크기, 수정일) 추출 모듈
import sqlite3    # 로컬 경량 데이터베이스(SQLite) 제어 모듈
import datetime   # 타임스탬프(숫자) 형태의 날짜를 읽기 쉬운 문자열로 변환하는 모듈

# =========================================================
# [2] 외부 제3자 라이브러리 불러오기 (External Libraries)
# =========================================================
import ollama                # 컴퓨터에 설치된 로컬 LLM(Ollama) 인공지능과 통신하는 모듈
from pypdf import PdfReader  # PDF 파일 내부의 텍스트 원문을 읽어내고 추출하는 모듈

# =========================================================
# [3] PySide6 (Qt GUI 그래픽 화면 제작 라이브러리) 부품 불러오기
# =========================================================
from PySide6.QtWidgets import (
    QApplication,    # PyQt/PySide 앱 전체 관리자 (모든 Qt 앱은 이게 필수)
    QMainWindow,     # 메인 창(Window) 틀을 만들어주는 클래스
    QWidget,         # 버튼, 테이블 등을 배치할 기본 레이아웃 바탕화면판
    QVBoxLayout,     # 위에서 아래(세로)로 부품들을 차곡차곡 정렬하는 레이아웃
    QHBoxLayout,     # 왼쪽에서 오른쪽(가로)으로 부품들을 차곡차곡 정렬하는 레이아웃
    QPushButton,     # 마우스로 클릭할 수 있는 버튼 부품
    QTableWidget,    # 엑셀처럼 표 형태로 데이터를 보여주는 테이블 부품
    QTableWidgetItem, # 테이블의 칸(셀) 하나하나에 들어갈 데이터 객체
    QFileDialog,     # 컴퓨터 내부의 폴더/파일을 선택할 수 있는 탐색기 창 부품
    QLabel,          # 화면에 텍스트 문구를 보여주는 라벨 부품
    QHeaderView,     # 테이블의 열(Column) 헤더 너비 및 자동 조절 정책 관리자
    QMessageBox      # 경고창, 완료창, 확인 알림창을 띄워주는 메시지 박스
)
from PySide6.QtCore import Qt, QUrl, QThread, Signal # 스레드, 신호, 유틸리티 기능
from PySide6.QtGui import QDesktopServices           # 시스템 기본 프로그램으로 파일 열기 기능

# 백엔드 DB 접속 객체나 비즈니스 로직이 담긴 커스텀 서비스 모듈 불러오기
from service import BackendService


# =========================================================
# [4] 백그라운드 스레드 클래스 (FolderScanAndTagWorker)
# ---------------------------------------------------------
# 이유: AI 분석 및 파일 스캔 작업을 메인 GUI 화면에서 처리하면
#      작업 중에 화면이 '응답 없음'으로 하얗게 굳어버립니다.
#      따라서 백그라운드(QThread)로 빼서 별도로 구동시킵니다.
# =========================================================
class FolderScanAndTagWorker(QThread):
    # 메인 GUI 화면과 통신하기 위한 신호(Signal) 통로 정의
    progress = Signal(str)  # 현재 스캔 및 분석 진행 상황 문구를 메인 화면으로 전달
    finished = Signal()     # 모든 파일의 스캔 및 태깅이 끝났음을 알리는 신호
    error = Signal(str)     # 작업 중 에러가 발생했을 때 에러 메시지를 전달하는 신호

    def __init__(self, folder_path, service, model_name="qwen2.5:3b"):
        """스레드가 생성될 때 필요한 초기 데이터를 전달받는 생성자 함수"""
        super().__init__()
        self.folder_path = folder_path  # 스캔할 폴더의 경로
        self.service = service          # 백엔드 서비스 객체
        self.model_name = model_name    # 사용할 Ollama 로컬 LLM 모델 이름

    def run(self):
        """worker.start()가 호출되면 백그라운드에서 실제 실행되는 메인 로직 함수"""
        try:
            # 1. 스캔 대상이 되는 파일 확장자 정의 (튜플 형태)
            valid_extensions = ('.txt', '.pdf')
            files_to_process = [] # 대상 파일들의 전체 경로를 담을 리스트
            
            # 2. 선택한 폴더 및 하위 폴더 전체를 재귀적으로 탐색 (os.walk)
            for root, _, files in os.walk(self.folder_path):
                for file in files:
                    # 파일명의 끝이 .txt 또는 .pdf로 끝나는지 확인 (소문자 변환 후 검사)
                    if file.lower().endswith(valid_extensions):
                        # 폴더 경로와 파일명을 합쳐서 완벽한 파일 경로 생성 후 리스트에 추가
                        files_to_process.append(os.path.join(root, file))

            # 3. 만약 조건에 맞는 파일이 하나도 없다면 에러 신호를 보내고 작업 종료
            if not files_to_process:
                self.error.emit("스캔할 지원 파일(.txt, .pdf)이 선택한 폴더에 없습니다.")
                return

            total_count = len(files_to_process) # 총 처리해야 할 파일 개수

            # 4. 파일 리스트를 하나씩 순회하며 분석 작업 수행
            for idx, file_path in enumerate(files_to_process, start=1):
                file_name = os.path.basename(file_path) # 전체 경로에서 pure 파일명만 추출
                
                # GUI 메인 화면으로 "분석 중 (1/10): file.txt" 형태의 메시지 전송
                self.progress.emit(f"분석 중 ({idx}/{total_count}): {file_name}")

                # [단계 A] 파일 본문 텍스트 추출
                content = self.extract_text(file_path)
                # [단계 B] 파일의 물리적 메타데이터(용량, 수정시간 등) 추출
                metadata = self.get_file_metadata(file_path)
                
                tags_and_comment = "내용을 읽을 수 없음" # 기본 초기화값

                # 텍스트 추출에 성공한 경우에만 AI 분석 진행
                if content:
                    # [단계 C] 메타데이터와 본문을 결합하여 AI에게 전달할 프롬프트 연성
                    prompt = f"""
다음 파일의 메타데이터와 본문 내용을 종합적으로 분석하여, 가장 적절한 태그 3개와 한 줄 요약 코멘트를 작성해라.

[파일 메타데이터]
- 파일명: {file_name}
- 파일 크기: {metadata['size']}
- 최종 수정일자: {metadata['modified_time']}
- 확장자: {metadata['extension']}

[출력 형식 예시]
태그: #데이터, #파이썬, #GUI / 코멘트: 파이썬 기반 GUI 프로그램 설계 문서입니다.

[문서 내용]
{content[:800]}
"""
                    try:
                        # [단계 D] Ollama 로컬 LLM 통신 요청 (속도 최적화 옵션 포함)
                        response = ollama.chat(
                            model=self.model_name,
                            messages=[{'role': 'user', 'content': prompt}],
                            options={
                                'num_predict': 60,  # 답변으로 생성할 최대 토큰 수 (속도 향상을 위해 제한)
                                'temperature': 0.2  # 창의성 수치 (낮을수록 일관되고 정돈된 답변을 출력)
                            }
                        )
                        # AI가 응답한 텍스트 결과물만 추출
                        tags_and_comment = response['message']['content']
                    except Exception as llm_err:
                        # Ollama가 안 꺼져있거나 통신 에러가 난 경우 에러 문구 남김
                        tags_and_comment = f"LLM 연동 실패: {llm_err}"

                # [단계 E] 분석된 결과를 SQLite 데이터베이스에 저장
                self.save_to_db(file_name, file_path, tags_and_comment)

            # 모든 파일 순회가 끝나면 완료 신호 전송
            self.finished.emit()

        except Exception as e:
            # 예상치 못한 시스템 예외 발생 시 에러 메시지 전송
            self.error.emit(f"스캔 및 태깅 작업 중 오류 발생: {str(e)}")

    def get_file_metadata(self, path):
        """파일의 물리적 정보(용량, 최종 수정일시, 확장자)를 추출하는 메타데이터 함수"""
        try:
            stat = os.stat(path) # OS 수준에서 파일 상태 정보 조회
            file_size_kb = round(stat.st_size / 1024, 2) # 바이트(Byte)를 KB 단위로 변환 후 소수점 2자리 반올림
            
            # 타임스탬프(숫자) 형태의 수정 시간을 'YYYY-MM-DD HH:MM:SS' 문자로 변환
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            return {
                "size": f"{file_size_kb} KB",
                "modified_time": mtime,
                "extension": os.path.splitext(path)[1].lower() # 확장자 추출 (예: .pdf)
            }
        except Exception:
            # 파일 접근 권한 문제 등으로 실패 시 예외 처리
            return {"size": "알 수 없음", "modified_time": "알 수 없음", "extension": "알 수 없음"}

    def extract_text(self, path):
        """파일 확장자에 따라 적절한 파서로 텍스트를 읽어오는 함수"""
        ext = os.path.splitext(path)[1].lower() # 확장자 추출
        try:
            if ext == '.txt':
                # TXT 파일: UTF-8 인코딩으로 오픈 (인코딩 에러는 무시)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            elif ext == '.pdf':
                # PDF 파일: pypdf 라이브러리의 PdfReader 이용
                reader = PdfReader(path)
                text = ""
                # PDF의 모든 페이지를 돌며 텍스트를 하나로 합침
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
        except Exception:
            return None # 읽기 실패 시 None 반환
        return None

    def save_to_db(self, file_name, file_path, ai_comment):
        """분석된 파일 정보를 SQLite 데이터베이스(file_manager.db)에 저장/업데이트하는 함수"""
        # DB 파일명 가져오기 (기본값: file_manager.db)
        db_path = getattr(self.service.db, 'db_name', 'file_manager.db')
        
        # DB 연결 및 커서 생성
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # files 테이블이 없으면 자동 생성 (ID, 파일명, 경로, AI코멘트, 카테고리)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                file_path TEXT UNIQUE,
                ai_comment TEXT,
                category TEXT
            )
        ''')

        # 파일 경로(file_path)가 유니크 키이므로, 기존에 존재하는 파일이면 UPDATE, 없으면 INSERT 적용
        cursor.execute('''
            INSERT INTO files (file_name, file_path, ai_comment, category)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_name=excluded.file_name,
                ai_comment=excluded.ai_comment
        ''', (file_name, file_path, ai_comment, "AI 태그 완료"))

        conn.commit() # 변경사항 실제 저장
        conn.close()  # DB 연결 종료


# =========================================================
# [5] 메인 GUI 화면 클래스 (MainWindow)
# =========================================================
class MainWindow(QMainWindow):
    def __init__(self):
        """메인 창이 처음 실행될 때 화면 구조 및 이벤트를 초기화하는 생성자"""
        super().__init__()
        self.service = BackendService() # 백엔드 서비스 연동

        # 메인 창 창 제목 및 초기 크기(가로 1000px, 세로 550px) 설정
        self.setWindowTitle("로컬 LLM 기반 파일 자동 태깅 & 메타데이터 Viewer")
        self.setGeometry(100, 100, 1000, 550)

        # PySide6 기본 중앙 위젯 세팅
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃: 위에서 아래로 정렬되는 수직 레이아웃(QVBoxLayout)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # ---------------------------------------------------------
        # [상단 상자 영역] 버튼 및 진행 상태 라벨 배치 (가로 레이아웃)
        # ---------------------------------------------------------
        top_layout = QHBoxLayout()
        
        # 1. 폴더 선택 및 태깅 시작 버튼
        self.btn_select_folder = QPushButton("📂 폴더 선택 및 LLM 태깅 시작")
        self.btn_select_folder.setStyleSheet("font-weight: bold; padding: 8px; background-color: #2196F3; color: white;")
        # 버튼 클릭 시 select_and_process_folder 함수 실행
        self.btn_select_folder.clicked.connect(self.select_and_process_folder)

        # 2. 현재 상태 표시 라벨 문구
        self.lbl_path = QLabel("선택된 폴더: 없음 (대기 중)")
        self.lbl_path.setStyleSheet("color: #444; font-weight: bold;")

        # 3. DB 초기화 버튼
        self.btn_reset = QPushButton("경로 및 DB 삭제")
        self.btn_reset.setStyleSheet("color: red; padding: 8px;")
        # 버튼 클릭 시 reset_db_and_path 함수 실행
        self.btn_reset.clicked.connect(self.reset_db_and_path)

        # 상단 레이아웃에 위젯들 순서대로 순척 추가
        top_layout.addWidget(self.btn_select_folder)
        top_layout.addWidget(self.lbl_path)
        top_layout.addStretch() # 중간에 공백(여백)을 밀어넣어 오른쪽 버튼을 끝으로 밀어냄
        top_layout.addWidget(self.btn_reset)

        # 메인 레이아웃에 상단 레이아웃 등록
        main_layout.addLayout(top_layout)

        # ---------------------------------------------------------
        # [하단 표 영역] 데이터베이스 결과를 보여주는 QTableWidget 배치
        # ---------------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(5) # 총 5개의 열(Column) 생성
        self.table.setHorizontalHeaderLabels(["ID", "파일명", "파일 경로", "로컬 LLM 분석 태그/코멘트", "카테고리"])
        
        # 표의 셀(항목)을 더블클릭했을 때 실행할 이벤트 연결 (파일 열기)
        self.table.itemDoubleClicked.connect(self.open_file_on_double_click)
        
        # 표의 열 너비 정책 설정
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID: 내용 길이에 맞춤
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # 파일명: 내용 길이에 맞춤
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # 파일 경로: 남은 여백 전부 차지
        header.setSectionResizeMode(3, QHeaderView.Stretch)          # LLM 분석: 남은 여백 전부 차지
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # 카테고리: 내용 길이에 맞춤

        main_layout.addWidget(self.table) # 메인 레이아웃에 테이블 추가

        # 앱이 켜지자마자 기존 DB에 저장되어 있던 데이터들을 읽어와 표에 채움
        self.load_db_to_table()

    def select_and_process_folder(self):
        """폴더 선택 창을 띄우고 백그라운드 스레드를 동작시키는 함수"""
        # 폴더 선택 팝업창을 띄우고 선택된 경로를 받아옴
        folder_path = QFileDialog.getExistingDirectory(self, "스캔 및 LLM 태깅을 진행할 폴더 선택")
        
        if folder_path:
            # 중복 클릭을 방지하기 위해 버튼 비활성화
            self.btn_select_folder.setEnabled(False)
            self.lbl_path.setText(f"선택된 폴더: {folder_path} (스캔 및 분석 준비 중...)")

            # 백그라운드 Worker 스레드 객체 생성
            self.worker = FolderScanAndTagWorker(folder_path, self.service, model_name="qwen2.5:3b")
            
            # 스레드의 신호(Signal)와 메인 화면의 슬롯(함수)들을 서로 연결
            self.worker.progress.connect(self.on_scan_progress) # 진행상황 신호 -> on_scan_progress
            self.worker.finished.connect(self.on_scan_finished) # 완료 신호 -> on_scan_finished
            self.worker.error.connect(self.on_scan_error)       # 에러 신호 -> on_scan_error
            
            # 스레드 구동 시작! (run() 메서드가 백그라운드에서 실행됨)
            self.worker.start()

    def on_scan_progress(self, status_text):
        """스레드가 한 파일씩 분석을 끝낼 때마다 화면 진행 상황과 표를 실시간 갱신"""
        self.lbl_path.setText(status_text)
        self.load_db_to_table() # DB 내용을 새로고침하여 표에 실시간 반영

    def on_scan_finished(self):
        """모든 스캔 및 태깅 작업이 완료되었을 때 실행되는 함수"""
        self.load_db_to_table() # 최종 DB 새로고침
        self.btn_select_folder.setEnabled(True) # 버튼 다시 활성화
        self.lbl_path.setText("상태: 모든 파일의 AI 태깅 분석 완료!")
        QMessageBox.information(self, "완료", "폴더 내부 파일 분석 및 로컬 LLM 태깅 저장이 완료되었습니다!")

    def on_scan_error(self, err_msg):
        """작업 도중 오류 발생 시 처리 함수"""
        self.btn_select_folder.setEnabled(True) # 버튼 다시 활성화
        self.lbl_path.setText("상태: 작업 중 오류 발생")
        QMessageBox.critical(self, "오류", err_msg) # 에러 알림 팝업창 출력

    def load_db_to_table(self):
        """SQLite DB 파일에서 저장된 목록을 조회해서 QTableWidget에 채워넣는 함수"""
        db_path = getattr(self.service.db, 'db_name', 'file_manager.db')
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # files 테이블에서 데이터 전체 조회
            cursor.execute("SELECT id, file_name, file_path, ai_comment, category FROM files")
            rows = cursor.fetchall() # 모든 결과 행을 가져옴
            conn.close()

            # 테이블의 전체 행(Row) 개수를 가져온 데이터 개수로 세팅
            self.table.setRowCount(len(rows))
            
            # 2차원 배열 형태로 데이터를 하나씩 읽어서 테이블의 각 셀에 대입
            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    # 사용자가 표의 셀 내용을 직접 수정하지 못하도록 읽기 전용(ReadOnly) 처리
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row_idx, col_idx, item)
        except Exception:
            self.table.setRowCount(0) # DB가 없거나 조회 실패 시 비어있는 표로 유지

    def reset_db_and_path(self):
        """DB 파일 자체를 물리적으로 삭제하고 테이블을 완전히 초기화하는 함수"""
        # 사용자에게 정말 삭제할 것인지 묻는 확인 MessageBox 출력
        reply = QMessageBox.question(
            self, 
            "DB 삭제 확인", 
            "정말로 저장된 파일 분석 DB를 삭제하고 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            db_path = getattr(self.service.db, 'db_name', 'file_manager.db')
            try:
                # 1. 파일 시스템에 기존 .db 파일이 존재하면 삭제
                if os.path.exists(db_path):
                    os.remove(db_path)
                
                # 2. 깨끗한 상태의 비어있는 DB 파일 및 테이블 다시 재생성
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT,
                        file_path TEXT UNIQUE,
                        ai_comment TEXT,
                        category TEXT
                    )
                ''')
                conn.commit()
                conn.close()

                # 3. 화면의 라벨 및 테이블 내용 초기화
                self.lbl_path.setText("선택된 폴더: 없음")
                self.table.setRowCount(0)
                QMessageBox.information(self, "초기화 완료", "DB 파일 삭제 및 경로 초기화가 완료되었습니다!")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"DB 삭제 중 오류 발생: {e}")

    def open_file_on_double_click(self, item: QTableWidgetItem):
        """테이블 항목을 더블클릭했을 때 운영체제의 기본 프로그램으로 해당 파일을 직접 열어주는 함수"""
        row = item.row() # 더블클릭한 셀의 행 번호
        file_path_item = self.table.item(row, 2) # 2번 열(파일 경로 Column) 데이터 가져오기
        
        if file_path_item:
            file_path = file_path_item.text() # 파일 경로 텍스트 추출
            if os.path.exists(file_path):
                # 파일 경로를 Qt 전용 QUrl 객체로 변환
                url = QUrl.fromLocalFile(file_path)
                # OS 기본 앱(메모장, PDF 뷰어 등)으로 해당 파일 실행
                QDesktopServices.openUrl(url)
            else:
                QMessageBox.warning(self, "경고", f"파일을 찾을 수 없습니다:\n{file_path}")


# =========================================================
# [6] 파이썬 프로그램 실행 엔트리 포인트
# =========================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)  # PySide6 실행 애플리케이션 생성
    window = MainWindow()         # 메인 창 객체 생성
    window.show()                 # 화면에 창 표시
    sys.exit(app.exec())          # 앱의 이벤트 루프 시작 및 종료 처리