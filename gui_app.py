# =========================================================
# [1] 파이썬 기본 표준 라이브러리 불러오기 (Import)
# =========================================================
import sys         # 파이썬 시스템 및 명령줄 인자 관리 (프로그램 종료 시 필요)
import os          # 파일 경로 접근, 폴더 탐색, 파일 메타데이터(크기, 수정일) 추출 모듈
import sqlite3     # 로컬 경량 데이터베이스(SQLite) 제어 모듈
import datetime    # 타임스탬프(숫자) 형태의 날짜를 읽기 쉬운 문자열로 변환하는 모듈
import io          # 바이너리 바이트 스트림 처리를 위한 모듈

# =========================================================
# [2] 외부 제3자 라이브러리 불러오기 (External Libraries)
# =========================================================
import ollama                # 컴퓨터에 설치된 로컬 LLM(Ollama) 인공지능과 통신하는 모듈
from pypdf import PdfReader  # PDF 파일 내부의 텍스트 원문을 읽어내고 추출하는 모듈
from PIL import Image        # 이미지 파일 읽기 및 바이트 변환 (한글 경로 지원용)
import numpy as np          # PIL -> OpenCV/Bytes 호환용

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
# =========================================================
class FolderScanAndTagWorker(QThread):
    progress = Signal(str)  # 현재 스캔 및 분석 진행 상황 문구를 메인 화면으로 전달
    finished = Signal()     # 모든 파일의 스캔 및 태깅이 끝났음을 알리는 신호
    error = Signal(str)     # 작업 중 에러가 발생했을 때 에러 메시지를 전달하는 신호

    def __init__(self, folder_path, service, text_model="qwen2.5:3b", vision_model="llava"):
        """스레드가 생성될 때 필요한 초기 데이터를 전달받는 생성자 함수"""
        super().__init__()
        self.folder_path = folder_path  # 스캔할 폴더의 경로
        self.service = service          # 백엔드 서비스 객체
        self.text_model = text_model    # 텍스트 문서용 Ollama 모델 이름
        self.vision_model = vision_model# 이미지 용 Ollama 비전 모델 이름 (안정적인 llava)

    def run(self):
        """worker.start()가 호출되면 백그라운드에서 실제 실행되는 메인 로직 함수"""
        try:
            # 1. 스캔 대상 확장자 (텍스트 + PDF + 이미지)
            text_exts = ('.txt', '.pdf')
            image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
            valid_extensions = text_exts + image_exts
            
            files_to_process = []
            
            # 2. 폴더 탐색 (하위 폴더까지 복사/스캔)
            for root, _, files in os.walk(self.folder_path):
                for file in files:
                    if file.lower().endswith(valid_extensions):
                        files_to_process.append(os.path.join(root, file))

            if not files_to_process:
                self.error.emit("스캔할 지원 파일(.txt, .pdf, 이미지)이 선택한 폴더에 없습니다.")
                return

            total_count = len(files_to_process)

            # 3. 파일 순회 분석
            for idx, file_path in enumerate(files_to_process, start=1):
                file_name = os.path.basename(file_path)
                ext = os.path.splitext(file_path)[1].lower()
                
                self.progress.emit(f"분석 중 ({idx}/{total_count}): {file_name}")

                metadata = self.get_file_metadata(file_path)
                tags_and_comment = "#분석실패 / 코멘트: 내용을 읽을 수 없습니다."

                # --- [A. 이미지 파일 분석 로직] ---
                if ext in image_exts:
                    try:
                        # PIL을 사용해 한글 경로 파일 안전하게 오픈 및 RGB 변환
                        with Image.open(file_path) as img:
                            img = img.convert("RGB")
                            img.thumbnail((768, 768)) # 경량화를 위해 가로세로 최대 768px 축소
                            
                            buffer = io.BytesIO()
                            img.save(buffer, format="JPEG", quality=80)
                            img_bytes = buffer.getvalue()

                        vision_prompt = "이 이미지의 핵심 내용을 분석해서 주요 태그 3개(#태그)와 한 줄 요약을 작성해줘."
                        
                        response = ollama.chat(
                            model=self.vision_model,
                            messages=[{
                                'role': 'user', 
                                'content': vision_prompt, 
                                'images': [img_bytes]
                            }],
                            options={'temperature': 0.2, 'num_predict': 150}
                        )
                        tags_and_comment = response.get('message', {}).get('content', '').strip()
                    except Exception as img_err:
                        tags_and_comment = f"Vision AI 분석 실패: {img_err}"

                # --- [B. 텍스트/PDF 문서 분석 로직] ---
                else:
                    content = self.extract_text(file_path)
                    if content:
                        prompt = f"""
다음 파일의 메타데이터와 본문 내용을 종합적으로 분석하여, 가장 적절한 태그 3개와 한 줄 요약 코멘트를 작성해라.

[파일 메타데이터]
- 파일명: {file_name}
- 파일 크기: {metadata['size']}
- 최종 수정일자: {metadata['modified_time']}

[출력 형식 예시]
태그: #데이터, #파이썬, #GUI / 코멘트: 파이썬 기반 GUI 프로그램 설계 문서입니다.

[문서 내용]
{content[:800]}
"""
                        try:
                            response = ollama.chat(
                                model=self.text_model,
                                messages=[{'role': 'user', 'content': prompt}],
                                options={'num_predict': 100, 'temperature': 0.2}
                            )
                            tags_and_comment = response.get('message', {}).get('content', '').strip()
                        except Exception as llm_err:
                            tags_and_comment = f"LLM 연동 실패: {llm_err}"

                # DB 저장
                self.save_to_db(file_name, file_path, tags_and_comment)

            self.finished.emit()

        except Exception as e:
            self.error.emit(f"스캔 및 태깅 작업 중 오류 발생: {str(e)}")

    def get_file_metadata(self, path):
        """파일의 메타데이터(크기, 수정시간, 확장자)를 구하는 함수"""
        try:
            stat = os.stat(path)
            file_size_kb = round(stat.st_size / 1024, 2)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            return {
                "size": f"{file_size_kb} KB",
                "modified_time": mtime,
                "extension": os.path.splitext(path)[1].lower()
            }
        except Exception:
            return {"size": "알 수 없음", "modified_time": "알 수 없음", "extension": "알 수 없음"}

    def extract_text(self, path):
        """TXT 및 PDF 문서 파일로부터 텍스트를 추출하는 함수"""
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == '.txt':
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            elif ext == '.pdf':
                reader = PdfReader(path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
        except Exception:
            return None
        return None

    def save_to_db(self, file_name, file_path, ai_comment):
        """분석된 결과를 SQLite DB 파일에 저장(Upsert)하는 함수"""
        db_path = getattr(self.service.db, 'db_name', 'file_manager.db')
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

        cursor.execute('''
            INSERT INTO files (file_name, file_path, ai_comment, category)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_name=excluded.file_name,
                ai_comment=excluded.ai_comment
        ''', (file_name, file_path, ai_comment, "AI 태그 완료"))

        conn.commit()
        conn.close()


# =========================================================
# [5] 메인 GUI 화면 클래스 (MainWindow)
# =========================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.service = BackendService()

        # 창 제목 및 초기 크기 설정
        self.setWindowTitle("로컬 멀티모달 LLM 기반 파일 자동 태깅 Viewer")
        self.setGeometry(100, 100, 1000, 550)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # [상단 영역: 버튼 및 경로 표시 라벨]
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

        # [하단 영역: 파일 데이터 표시용 테이블]
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        # 테이블 컬럼 헤더 설정 (Index 0: ID, 1: 파일명, 2: 파일 경로, 3: 코멘트, 4: 카테고리)
        self.table.setHorizontalHeaderLabels(["ID", "파일명", "파일 경로", "로컬 LLM/Vision 분석 코멘트", "카테고리"])
        
        # 테이블의 셀을 더블클릭했을 때 반응할 연결 함수(이벤트) 설정
        self.table.itemDoubleClicked.connect(self.open_file_on_double_click)
        
        # 테이블 내 텍스트가 셀 너비를 넘어가도 잘리지 않고 자동 줄바꿈되도록 설정
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
        """'폴더 선택' 버튼 클릭 시 탐색기를 띄우고 스레드를 시작하는 함수"""
        folder_path = QFileDialog.getExistingDirectory(self, "스캔 및 AI 태깅을 진행할 폴더 선택")
        
        if folder_path:
            self.btn_select_folder.setEnabled(False)
            self.lbl_path.setText(f"선택된 폴더: {folder_path} (AI 모델 분석 준비 중...)")

            # 백그라운드 Worker 스레드 생성 및 실행
            self.worker = FolderScanAndTagWorker(
                folder_path=folder_path, 
                service=self.service, 
                text_model="qwen2.5:3b",
                vision_model="llava"
            )
            
            self.worker.progress.connect(self.on_scan_progress)
            self.worker.finished.connect(self.on_scan_finished)
            self.worker.error.connect(self.on_scan_error)
            
            self.worker.start()

    def on_scan_progress(self, status_text):
        """스레드가 작업 중 진행 상태를 보낼 때 UI 라벨과 테이블을 갱신하는 함수"""
        self.lbl_path.setText(status_text)
        self.load_db_to_table()

    def on_scan_finished(self):
        """모든 분석 작업이 정상 종료되었을 때 호출되는 함수"""
        self.load_db_to_table()
        self.btn_select_folder.setEnabled(True)
        self.lbl_path.setText("상태: 모든 파일의 고정밀 AI 분석 완료!")
        QMessageBox.information(self, "완료", "폴더 내부 파일 분석 및 로컬 AI 태깅 저장이 완료되었습니다!")

    def on_scan_error(self, err_msg):
        """작업 도중 오류가 발생했을 때 호출되는 함수"""
        self.btn_select_folder.setEnabled(True)
        self.lbl_path.setText("상태: 작업 중 오류 발생")
        QMessageBox.critical(self, "오류", err_msg)

    def load_db_to_table(self):
        """SQLite DB 파일에 저장된 태깅 정보를 읽어서 화면의 QTableWidget 표에 채워 넣는 함수"""
        db_path = getattr(self.service.db, 'db_name', 'file_manager.db')
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, file_name, file_path, ai_comment, category FROM files")
            rows = cursor.fetchall()
            conn.close()

            self.table.setRowCount(len(rows))
            
            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 셀 내용 직접 수정 불가 처리
                    self.table.setItem(row_idx, col_idx, item)
        except Exception:
            self.table.setRowCount(0)

    def reset_db_and_path(self):
        """DB 데이터 삭제 및 리셋 함수"""
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
                if os.path.exists(db_path):
                    os.remove(db_path)
                
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

                self.lbl_path.setText("선택된 폴더: 없음")
                self.table.setRowCount(0)
                QMessageBox.information(self, "초기화 완료", "DB 파일 삭제 및 경로 초기화가 완료되었습니다!")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"DB 삭제 중 오류 발생: {e}")

    def open_file_on_double_click(self, item: QTableWidgetItem):
        """[핵심 수정] 테이블 내 특정 셀을 더블클릭했을 때 발생하는 이벤트 함수
        
        - 클릭한 위치(Column)가 3번 열(로컬 LLM/Vision 분석 코멘트)인 경우:
          -> 잘린 전체 문장을 모달 팝업 메시지창(QMessageBox)으로 보여줍니다.
        - 그 외의 열(예: 파일 경로 등)을 클릭한 경우:
          -> 해당 파일 경로를 찾아 기본 윈도우 프로그램으로 오픈합니다.
        """
        row = item.row()     # 사용자가 더블클릭한 행(Row) 번호 (0, 1, 2, ...)
        col = item.column()  # 사용자가 더블클릭한 열(Column) 번호 (0: ID, 1: 파일명, 2: 파일경로, 3: 코멘트)

        # 1. 사용자가 더블클릭한 칸이 '3번 열(AI 코멘트)'인 경우
        if col == 3:
            file_name_item = self.table.item(row, 1)  # 같은 행의 1번 열(파일명) 추출
            file_name = file_name_item.text() if file_name_item else "알 수 없는 파일"
            comment_text = item.text()                 # 현재 더블클릭한 3번 셀의 전체 텍스트 원문

            # 전체 내용 표시용 팝업 메시지 창 생성
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"상세 분석 결과 - {file_name}")
            msg_box.setText(comment_text)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec()  # 팝업창 출력

        # 2. 그 외의 열(특히 2번 열: 파일 경로)을 더블클릭한 경우 (기존 파일 실행 로직)
        else:
            file_path_item = self.table.item(row, 2)  # 같은 행의 2번 열(파일 경로) 추출
            if file_path_item:
                file_path = file_path_item.text()
                if os.path.exists(file_path):
                    # 시스템 기본 응용프로그램으로 연결하여 파일 실행
                    url = QUrl.fromLocalFile(file_path)
                    QDesktopServices.openUrl(url)
                else:
                    QMessageBox.warning(self, "경고", f"파일을 찾을 수 없습니다:\n{file_path}")


# =========================================================
# [6] 실행 엔트리 포인트
# =========================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())