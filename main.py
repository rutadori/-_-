# ========================================================================================
# [모듈 이름] main.py
# [모듈 역할] PySide6 기반 Desktop GUI 화면 구성, 사용자 이벤트 처리 및 비동기 작업 스레드 관리
#
# [이 모듈이 존재하는 이유]
# 1. 사용자 인터페이스(UI) 제공:
#    CUI/터미널 환경에 익숙하지 않은 사용자도 버튼 클릭과 표(Table) 형태로 
#    폴더 스캔 및 AI 분석 결과를 직관적으로 확인하고 제어할 수 있게 합니다.
# 2. 메인 스레드 멈춤 방지 (QThread 활용 비동기 처리):
#    폴더 스캔, AI(Ollama) 연동, DB 작업과 같이 시간이 걸리는 백엔드 프로세스를
#    독립된 백그라운드 스레드에서 구동하여 GUI 화면이 '응답 없음'으로 프리징되는 현상을 막습니다.
# 3. 프론트엔드-백엔드 데이터 동기화:
#    백엔드 처리 완료 신호(Signal)를 수신하면 SQLite DB에 반영된 최신 분석 내역을 
#    자동으로 불러와 테이블 위젯을 즉시 갱신합니다.
# ========================================================================================

import sys
# PySide6(GUI 라이브러리)에서 필요한 화면 구성 요소 및 스레드 모듈을 가져옵니다.
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox
)
from PySide6.QtCore import QThread, Signal

# 백엔드 통합 서비스를 가져옵니다. (service.py 파일의 BackendService 클래스)
from service import BackendService


# =========================================================
# [1] 백그라운드 작업용 스레드 클래스 (GUI 멈춤 방지용)
# =========================================================
class FolderProcessingThread(QThread):
    """
    [비동기 작업 스레드]
    
    ■ 존재 이유:
      폴더 스캔, 텍스트 추출, AI 분석 및 DB 저장 작업은 시간이 오래 걸립니다.
      이 작업을 화면(Main Thread)에서 그대로 실행하면 분석하는 동안 프로그램 창이
      '응답 없음'으로 멈추게 됩니다.
      이를 방지하기 위해 백그라운드 전용 일꾼(QThread)을 따로 만들어 일을 시킵니다.
    """
    # 작업이 모두 끝났을 때 main.py 화면으로 "완료되었다"고 알림을 보낼 신호(Signal)
    finished_signal = Signal()

    def __init__(self, folder_path: str):
        super().__init__()
        # 사용자가 선택한 폴더 경로를 받아와서 보관해 둡니다.
        self.folder_path = folder_path
        # 백엔드 로직을 실행할 엔진 객체를 준비합니다.
        self.backend_service = BackendService()

    def run(self):
        """
        [스레드 실행 메서드]
        .start()가 호출되면 백그라운드 독립 공간에서 이 메서드가 자동으로 실행됩니다.
        """
        # 백엔드 엔진의 폴더 일괄 처리(스캔 -> 텍스트추출 -> AI분석 -> DB저장) 실행
        self.backend_service.process_folder(self.folder_path)
        
        # 작업이 끝나면 화면(Main GUI) 쪽에 작업 종료 신호를 보냅니다.
        self.finished_signal.emit()


# =========================================================
# [2] 메인 GUI 창 클래스 (사용자 화면 관리)
# =========================================================
class MainWindow(QMainWindow):
    """
    [메인 윈도우 창 클래스]
    
    ■ 역할:
      사용자의 눈에 보이는 창(Window), 버튼, 테이블(표) UI를 생성하고
      버튼 클릭 이벤트를 받아 백엔드 스레드를 구동하며, 
      완료 후 DB의 최신 결과를 화면 표에 출력합니다.
    """
    def __init__(self):
        super().__init__()
        # 1. 메인 창의 기본 설정 (제목, 초기 크기)
        self.setWindowTitle("AI 파일 자동 분석 및 분류 시스템")
        self.resize(800, 600)

        # 2. 백엔드 서비스 객체 (DB 조회를 위해 준비)
        self.backend_service = BackendService()
        
        # 3. 스레드 객체를 담아둘 변수 초기화
        self.worker_thread = None

        # 4. GUI 화면 구성 요소(레이아웃 및 위젯) 초기화 실행
        self.init_ui()

    def init_ui(self):
        """
        [화면 레이아웃 및 버튼/테이블 배치 함수]
        """
        # 창의 중앙에 들어갈 기본 메인 위젯 및 수직(위->아래) 레이아웃 생성
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # --- [위젯 1] 폴더 선택 및 분석 시작 버튼 ---
        self.btn_select_folder = QPushButton("📂 분석할 폴더 선택하기")
        # 버튼을 클릭하면 self.on_select_folder_click 함수가 실행되도록 연결(Connect)
        self.btn_select_folder.clicked.connect(self.on_select_folder_click)
        layout.addWidget(self.btn_select_folder)

        # --- [위젯 2] DB 결과를 시각적으로 보여줄 표(Table) ---
        self.table_widget = QTableWidget()
        # 표의 열(Column) 개수를 4개로 지정
        self.table_widget.setColumnCount(4)
        # 각 열의 헤더(제목) 설정
        self.table_widget.setHorizontalHeaderLabels(["ID", "파일명", "AI 카테고리", "AI 분석 코멘트"])
        layout.addWidget(self.table_widget)

        # 프로그램 실행 시 기존 DB에 저장되어 있던 데이터를 먼저 화면 표에 로드
        self.load_data_to_table()

    def on_select_folder_click(self):
        """
        [폴더 선택 버튼 클릭 시 실행되는 이벤트 함수]
        """
        # 1. 윈도우 폴더 선택 창을 띄워 사용자에게 폴더 경로를 받아옴
        selected_folder = QFileDialog.getExistingDirectory(self, "분석할 폴더를 선택하세요")

        # 사용자가 취소하지 않고 폴더를 정상적으로 선택한 경우
        if selected_folder:
            # 작업 중 추가 클릭을 방지하기 위해 버튼 비활성화
            self.btn_select_folder.setEnabled(False)
            self.btn_select_folder.setText("⏳ AI 분석 및 DB 저장 진행 중...")

            # 2. 백그라운드 전용 스레드 객체 생성
            self.worker_thread = FolderProcessingThread(selected_folder)
            
            # 3. 백그라운드 작업 완료 신호(finished_signal)가 넘어오면 
            #    self.on_processing_finished 함수를 실행하라고 등록
            self.worker_thread.finished_signal.connect(self.on_processing_finished)
            
            # 4. 스레드 구동 시작 (QThread의 run() 메서드가 백그라운드에서 호출됨)
            self.worker_thread.start()

    def on_processing_finished(self):
        """
        [백엔드 작업 스레드가 완료되었을 때 실행되는 콜백 함수]
        """
        # 1. 버튼 상태 복원
        self.btn_select_folder.setEnabled(True)
        self.btn_select_folder.setText("📂 분석할 폴더 선택하기")

        # 2. DB에 새로 저장된 데이터를 가져와 화면 표(Table)에 다시 그리기
        self.load_data_to_table()

        # 3. 사용자에게 완결 알림 팝업 창 표시
        QMessageBox.information(self, "완료", "선택한 폴더의 AI 분석 및 DB 저장이 완료되었습니다!")

    def load_data_to_table(self):
        """
        [DB에서 모든 파일 데이터를 읽어와 화면 표(Table)에 채우는 함수]
        """
        # service.py -> database.py를 통해 DB에 저장된 모든 데이터 행 목록 조회
        # 조회 결과 구조: [(id, file_name, file_path, ai_category, ai_tags, ai_comment), ...]
        all_records = self.backend_service.db.get_all_files()

        # 표의 행(Row) 수를 DB 데이터 개수만큼 설정
        self.table_widget.setRowCount(len(all_records))

        # DB 데이터 행(row_idx)을 하나씩 읽으며 표의 각 셀(col)에 채움
        for row_idx, record in enumerate(all_records):
            # record에서 필요한 컬럼 값을 추출
            db_id = str(record[0])          # ID (숫자 -> 문자열 변환)
            file_name = str(record[1])      # 파일명
            ai_category = str(record[3])    # AI 카테고리
            ai_comment = str(record[5]) if len(record) > 5 else ""  # AI 코멘트

            # 표(QTableWidget) 각 칸에 들어갈 아이템 객체 생성 및 배치
            self.table_widget.setItem(row_idx, 0, QTableWidgetItem(db_id))
            self.table_widget.setItem(row_idx, 1, QTableWidgetItem(file_name))
            self.table_widget.setItem(row_idx, 2, QTableWidgetItem(ai_category))
            self.table_widget.setItem(row_idx, 3, QTableWidgetItem(ai_comment))


# =========================================================
# [3] 프로그램 전체 실행 진입점 (Main Entry Point)
# =========================================================
if __name__ == "__main__":
    # PySide6 애플리케이션 생성 (시스템 이벤트 루프 관리)
    app = QApplication(sys.argv)

    # 메인 GUI 창 생성 및 화면에 표시
    window = MainWindow()
    window.show()

    # 사용자가 창을 닫을 때까지 이벤트 루프를 계속 실행하며 유지
    sys.exit(app.exec())