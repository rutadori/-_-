# =========================================================
# [gui_app.py] 
# PySide6 기반 GUI 뷰어 및 백그라운드 스레드 제어 모듈
# 
# ---------------------------------------------------------
# 🌟 [주요 변경 히스토리 및 개선 사항]
# ---------------------------------------------------------
# 1. 역할 분리 (Separation of Concerns)
#    - 기존: GUI 스레드 내에서 AI 통신, 텍스트 파싱, DB 저장을 직접 처리하여 비대했음.
#    - 최종: 'MainProcessor' 관제탑 도입. GUI는 파일 스캔/경로 탐색만 수행하고, 
#            실제 AI 분석 및 데이터 처리는 백엔드 모듈로 완벽히 위임(Delegation).
#
# 2. 자연어 검색 및 라우팅 (Intent Routing) 추가
#    - 'SearchQueryParser' 및 'SearchEngine' 결합. 
#    - 사용자의 자연어 입력을 받아 AI가 의도(@검색, @대화)를 분석하고, 
#      그에 따라 실시간으로 테이블을 갱신하거나 챗 팝업을 띄우는 라우팅 로직 구현.
#
# 3. 윈도우 환경 대응 및 경로 정규화 (Robust Path Handling)
#    - 경로 깨짐(￥ vs \) 현상 방지: os.path.normpath/abspath 적용으로 안정적 경로 확보.
#    - 시스템 환경에 관계없이 일관된 파일 존재 여부 검사 및 실행 지원.
#
# 4. 프로세스 잠금(WinError 32) 원천 차단
#    - 기존: os.remove()로 DB 파일을 물리 삭제하여 파일 점유 에러 발생.
#    - 최종: SQL DELETE 문 및 sqlite_sequence 초기화 방식으로 DB를 리셋하여 
#            프로세스 점유 없이 안전하게 데이터만 초기화하도록 개선.
# =========================================================

import sys         
import os          
import sqlite3     
import json        # 🌟 [추가] AI 파싱 및 검색 결과 JSON 처리용

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QFileDialog,
    QLabel, QHeaderView, QMessageBox, QLineEdit  # 🌟 [추가] 자연어 입력용 QLineEdit
)
from PySide6.QtCore import Qt, QUrl, QThread, Signal 
from PySide6.QtGui import QDesktopServices           

# ---------------------------------------------------------
# 백엔드 및 모듈 연동 (역할 분리 및 파이프라인 통합)
# ---------------------------------------------------------
from service import BackendService
from file_pipeline import TextExtractor, FileAnalyzer
from main_processor import MainProcessor  # 🌟 [변경] 통합 백엔드 관제탑 모듈 결합

# 자연어 파서 및 검색 엔진 안전 로딩
try:
    from query_parser import SearchQueryParser
    HAS_QUERY_PARSER = True
except ImportError:
    HAS_QUERY_PARSER = False

try:
    from search_engine import SearchEngine
    HAS_SEARCH_ENGINE = True
except ImportError:
    HAS_SEARCH_ENGINE = False


# =========================================================
# [4] 폴더 스캔 및 태깅 백그라운드 스레드 (FolderScanAndTagWorker)
# =========================================================
class FolderScanAndTagWorker(QThread):
    progress = Signal(str)  
    finished = Signal()     
    error = Signal(str)     

    def __init__(self, folder_path, main_processor: MainProcessor, service): # 🌟 [변경] service 단독에서 MainProcessor 주입 방식으로 변경
        super().__init__()
        self.folder_path = folder_path
        self.main_processor = main_processor
        self.service = service

    def run(self):
        try:
            # 🌟 [확장] 문서, 이미지뿐만 아니라 미디어(.mp3, .mp4 등) 확장자까지 대폭 수용
            valid_extensions = (
                '.txt', '.pdf', '.docx', '.xlsx', '.pptx', '.hwp', '.hwpx',
                '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif',
                '.mp3', '.mp4', '.wav', '.m4a', '.mkv', '.avi'
            )
            
            files_to_process = []
            for root, _, files in os.walk(self.folder_path):
                for file in files:
                    if file.lower().endswith(valid_extensions):
                        full_path = os.path.join(root, file)
                        # 🌟 [핵심] 경로 깨짐 현상 및 슬래시 정규화 처리
                        clean_path = full_path.replace('￥', '/').replace('\\', '/')
                        clean_path = os.path.abspath(os.path.normpath(clean_path))
                        files_to_process.append(clean_path)

            if not files_to_process:
                self.error.emit("스캔할 지원 파일이 선택한 폴더에 없습니다.")
                return

            total_count = len(files_to_process)

            # 🌟 [변경] 기존에 스레드 안에서 직접 ollama를 호출하던 로직을 제거하고,
            # MainProcessor에 일임하여 백엔드 파이프라인이 전담하도록 구조 변경됨
            for idx, file_path in enumerate(files_to_process, start=1):
                file_name = os.path.basename(file_path)
                self.progress.emit(f"백엔드 AI 분석 중 ({idx}/{total_count}): {file_name}")
                
                self.main_processor.process_file_upload(file_path)

            self.finished.emit()

        except Exception as e:
            self.error.emit(f"스캔 및 태깅 작업 중 오류 발생: {str(e)}")


# =========================================================
# [5] 자연어 파싱 전용 백그라운드 스레드 (QueryParseWorker) - 🌟 [신규 추가]
# =========================================================
class QueryParseWorker(QThread):
    """자연어 검색어 입력 시 UI 멈춤을 방지하기 위한 비동기 파싱 스레드"""
    finished = Signal(dict) 
    error = Signal(str)     

    def __init__(self, user_text, query_parser):
        super().__init__()
        self.user_text = user_text
        self.query_parser = query_parser

    def run(self):
        try:
            result = self.query_parser.parse_user_query(self.user_text)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"자연어 파싱 처리 중 오류: {str(e)}")


# =========================================================
# [6] 메인 GUI 화면 클래스 (MainWindow)
# =========================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.service = BackendService()
        self.db_path = getattr(self.service.db, 'db_name', 'file_manager.db')

        # 🌟 [신규] 백엔드 관제탑 및 분석 부품 초기화 결합
        self.extractor = TextExtractor(max_chars=2000)
        self.analyzer = FileAnalyzer(text_model="qwen2.5:3b", vision_model="llava")
        
        self.query_parser = SearchQueryParser(model="qwen2.5:3b") if HAS_QUERY_PARSER else None
        
        self.main_processor = MainProcessor(
            extractor=self.extractor,
            analyzer=self.analyzer,
            query_parser=self.query_parser,
            db_path=self.db_path
        )

        self.search_engine = SearchEngine(db_path=self.db_path) if HAS_SEARCH_ENGINE else None

        self.setWindowTitle("로컬 멀티모달 LLM 기반 파일 자동 태깅 Viewer")
        self.setGeometry(100, 100, 1100, 650) # 창 크기 확장

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # 🌟 [신규] A. 상단 자연어 검색어 영역 추가
        search_layout = QHBoxLayout()
        self.lbl_search = QLabel("💬 자연어 검색:")
        self.lbl_search.setStyleSheet("font-weight: bold;")
        
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("예: 지난주 작성한 프로젝트 pdf 파일 찾아줘 / 오늘 날씨 어때?")
        self.input_search.setStyleSheet("padding: 6px; font-size: 13px;")
        self.input_search.returnPressed.connect(self.test_query_parsing)

        self.btn_parse = QPushButton("🔍 AI 검색 / 대화 실행")
        self.btn_parse.setStyleSheet("font-weight: bold; padding: 6px 12px; background-color: #4CAF50; color: white;")
        self.btn_parse.clicked.connect(self.test_query_parsing)

        self.btn_show_all = QPushButton("🔄 전체 목록 보기")
        self.btn_show_all.setStyleSheet("padding: 6px; background-color: #757575; color: white;")
        self.btn_show_all.clicked.connect(self.load_db_to_table)

        search_layout.addWidget(self.lbl_search)
        search_layout.addWidget(self.input_search)
        search_layout.addWidget(self.btn_parse)
        search_layout.addWidget(self.btn_show_all)
        main_layout.addLayout(search_layout)

        # B. 중단 폴더 선택 및 DB 제어 영역
        top_layout = QHBoxLayout()
        self.btn_select_folder = QPushButton("📂 폴더 선택 및 고정밀 AI 태깅 시작")
        self.btn_select_folder.setStyleSheet("font-weight: bold; padding: 8px; background-color: #2196F3; color: white;")
        self.btn_select_folder.clicked.connect(self.select_and_process_folder)

        self.lbl_path = QLabel("선택된 폴더: 없음 (대기 중)")
        self.lbl_path.setStyleSheet("color: #444; font-weight: bold;")

        self.btn_reset = QPushButton("경로 및 DB 삭제")
        self.btn_reset.setStyleSheet("color: red; padding: 8px;")
        self.btn_reset.clicked.connect(self.reset_db_and_path)

        top_layout.addWidget(self.btn_select_folder)
        top_layout.addWidget(self.lbl_path)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_reset)
        main_layout.addLayout(top_layout)

        # C. 하단 파일 목록 디스플레이 표(Table) 영역
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "파일명", "파일 경로", "로컬 LLM/Vision 분석 코멘트", "카테고리"])
        self.table.itemDoubleClicked.connect(self.open_file_on_double_click)
        self.table.setWordWrap(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        main_layout.addWidget(self.table)
        self.load_db_to_table()

    def select_and_process_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "스캔 및 AI 태깅을 진행할 폴더 선택")
        if folder_path:
            clean_folder_path = folder_path.replace('￥', '/').replace('\\', '/')
            clean_folder_path = os.path.abspath(os.path.normpath(clean_folder_path))
            
            self.btn_select_folder.setEnabled(False)
            self.lbl_path.setText(f"선택된 폴더: {clean_folder_path} (백엔드 파이프라인 분석 준비 중...)")

            # 🌟 [변경] MainProcessor 인스턴스를 스레드에 전달하도록 수정됨
            self.worker = FolderScanAndTagWorker(
                folder_path=clean_folder_path,
                main_processor=self.main_processor,
                service=self.service
            )
            self.worker.progress.connect(self.on_scan_progress)
            self.worker.finished.connect(self.on_scan_finished)
            self.worker.error.connect(self.on_scan_error)
            self.worker.start()

    def on_scan_progress(self, status_text):
        self.lbl_path.setText(status_text)
        self.load_db_to_table()

    def on_scan_finished(self):
        self.load_db_to_table()
        self.btn_select_folder.setEnabled(True)
        self.lbl_path.setText("상태: 모든 파일의 백엔드 AI 분석 및 태깅 완료!")
        QMessageBox.information(self, "완료", "폴더 내부 파일 분석 및 로컬 AI 태깅 저장이 완료되었습니다!")

    def on_scan_error(self, err_msg):
        self.btn_select_folder.setEnabled(True)
        self.lbl_path.setText("상태: 작업 중 오류 발생")
        QMessageBox.critical(self, "오류", err_msg)

    # ---------------------------------------------------------
    # 🌟 [신규 추가] 자연어 검색 및 파싱 이벤트 핸들러 메서드들
    # ---------------------------------------------------------
    def test_query_parsing(self):
        user_text = self.input_search.text().strip()
        if not user_text:
            QMessageBox.warning(self, "경고", "검색어나 대화 내용을 입력해 주세요.")
            return

        if not HAS_QUERY_PARSER or self.query_parser is None:
            QMessageBox.critical(self, "오류", "query_parser.py 모듈을 찾을 수 없습니다.")
            return

        self.btn_parse.setEnabled(False)
        self.btn_parse.setText("⏳ AI 처리 중...")

        self.parse_worker = QueryParseWorker(user_text, self.query_parser)
        self.parse_worker.finished.connect(self.on_query_parse_finished)
        self.parse_worker.error.connect(self.on_query_parse_error)
        self.parse_worker.start()

    def on_query_parse_finished(self, result_dict):
        self.btn_parse.setEnabled(True)
        self.btn_parse.setText("🔍 AI 검색 / 대화 실행")

        parsed_data = result_dict.get("data", {})
        if HAS_SEARCH_ENGINE and self.search_engine:
            execution_result = self.search_engine.process_query_result(parsed_data)
            action = execution_result.get("action")
            message = execution_result.get("message", "")
            data_list = execution_result.get("data", [])

            if action == "UPDATE_TABLE":
                self.update_table_with_search_results(data_list)
                self.lbl_path.setText(f"검색 결과: {message}")
            elif action == "SHOW_CHAT":
                QMessageBox.information(self, "🤖 AI 대화 응답", message)
            else:
                QMessageBox.warning(self, "알림", f"처리 결과: {message}")
        else:
            formatted_json = json.dumps(result_dict, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "파싱 결과", formatted_json)

    def on_query_parse_error(self, err_msg):
        self.btn_parse.setEnabled(True)
        self.btn_parse.setText("🔍 AI 검색 / 대화 실행")
        QMessageBox.critical(self, "파싱 오류", err_msg)

    def update_table_with_search_results(self, rows):
        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

    def load_db_to_table(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, file_name, file_path, ai_comment, category FROM files")
            rows = cursor.fetchall()
            conn.close()

            self.table.setRowCount(len(rows))
            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row_idx, col_idx, item)
            
            self.lbl_path.setText("상태: 전체 DB 파일 목록 출력 중")
        except Exception:
            self.table.setRowCount(0)

    # ---------------------------------------------------------
    # 🌟 [핵심 변경] WinError 32 점유 에러 방어용 SQL 초기화 로직
    # ---------------------------------------------------------
    def reset_db_and_path(self):
        """
        - 기존: os.remove(db_path)를 사용하여 물리 파일을 삭제하려다 프로세스 점유로 WinError 32 발생
        - 수정: 파일을 지우지 않고 SQL DELETE문과 sqlite_sequence를 초기화하여 에러를 근본적으로 방어
        """
        reply = QMessageBox.question(
            self, "DB 삭제 확인", 
            "정말로 저장된 파일 분석 DB를 삭제하고 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT, file_path TEXT UNIQUE, ai_comment TEXT, category TEXT)")
                cursor.execute("DELETE FROM files;")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='files';") # ID 인덱스 리셋
                conn.commit()
                conn.close() # 명시적 세션 종료

                self.lbl_path.setText("선택된 폴더: 없음")
                self.table.setRowCount(0)
                QMessageBox.information(self, "초기화 완료", "DB 데이터 및 상태 초기화가 성공적으로 완료되었습니다!")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"DB 초기화 처리 중 오류 발생: {str(e)}")

    def open_file_on_double_click(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()

        if col == 3:
            file_name_item = self.table.item(row, 1)
            file_name = file_name_item.text() if file_name_item else "알 수 없는 파일"
            comment_text = item.text()

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"상세 분석 결과 - {file_name}")
            msg_box.setText(comment_text)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec()
        else:
            file_path_item = self.table.item(row, 2)
            if file_path_item:
                raw_file_path = file_path_item.text()
                # 🌟 [개선] 경로 문자 정제 후 파일 존재 여부 검사 및 실행
                clean_path = raw_file_path.replace('￥', '/').replace('\\', '/')
                clean_path = os.path.abspath(os.path.normpath(clean_path))

                if os.path.exists(clean_path):
                    url = QUrl.fromLocalFile(clean_path)
                    QDesktopServices.openUrl(url)
                else:
                    QMessageBox.warning(self, "경고", f"파일을 찾을 수 없습니다:\n{clean_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())