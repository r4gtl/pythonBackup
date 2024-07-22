import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QTimeEdit, QLabel, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QHBoxLayout
from PyQt5.QtCore import QDate, QTime, QThread, pyqtSignal
import schedule
import time
import threading
import shutil
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from db.models import Session, BackupJob, Path, create_tables
from dotenv import load_dotenv

load_dotenv()


# Recupera le credenziali dalle variabili d'ambiente
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')


class BackupThread(QThread):
    progress = pyqtSignal(int)
    current_file = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, source_paths, dest_folder, send_email):
        super().__init__()
        self.source_paths = source_paths
        self.dest_folder = dest_folder
        self.send_email = send_email

    def run(self):
        try:
            self.dest_folder = os.path.join(self.dest_folder, 'backup')
            if not os.path.exists(self.dest_folder):
                os.makedirs(self.dest_folder)

            total_files = sum([len(files) for path in self.source_paths for r, d, files in os.walk(path)])
            copied_files = 0

            for source_folder in self.source_paths:
                for root, dirs, files in os.walk(source_folder):
                    relative_path = os.path.relpath(root, source_folder)
                    dest_dir = os.path.join(self.dest_folder, relative_path)

                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)

                    for file in files:
                        src_file = os.path.join(root, file)
                        dest_file = os.path.join(dest_dir, file)

                        if not os.path.exists(dest_file) or os.path.getmtime(src_file) > os.path.getmtime(dest_file):
                            shutil.copy2(src_file, dest_file)
                            copied_files += 1
                            self.progress.emit(int(copied_files / total_files * 100))
                            self.current_file.emit(src_file)

            self.finished.emit(True)
        except Exception as e:
            self.finished.emit(False)
            print(f"Error during backup: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        create_tables()
        self.initUI()
        self.session = Session()
        self.load_backup_settings()

    def initUI(self):
        self.setWindowTitle('Backup Manager')

        layout = QVBoxLayout()

        self.source_button = QPushButton('Select Source Folders/Files')
        self.source_button.clicked.connect(self.select_source_paths)
        layout.addWidget(self.source_button)

        self.source_table = QTableWidget(0, 1)
        self.source_table.setHorizontalHeaderLabels(['Paths'])
        self.source_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.source_table)

        self.dest_button = QPushButton('Select Destination Folder')
        self.dest_button.clicked.connect(self.select_dest_folder)
        layout.addWidget(self.dest_button)

        self.time_edit = QTimeEdit(self)
        self.time_edit.setTime(QTime.currentTime())
        layout.addWidget(self.time_edit)

        self.days_layout = QHBoxLayout()
        self.days_checkboxes = {}
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days:
            checkbox = QCheckBox(day)
            self.days_checkboxes[day] = checkbox
            self.days_layout.addWidget(checkbox)
        layout.addLayout(self.days_layout)

        self.send_email_checkbox = QCheckBox('Send Email on Completion')
        layout.addWidget(self.send_email_checkbox)

        self.add_backup_btn = QPushButton('Add Backup')
        self.add_backup_btn.clicked.connect(self.add_backup)
        layout.addWidget(self.add_backup_btn)

        self.status_label = QLabel('Status: Ready')
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar(self)
        layout.addWidget(self.progress_bar)

        self.current_file_label = QLabel('Current file: None')
        layout.addWidget(self.current_file_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.source_paths = []
        self.dest_folder = ""

    def select_source_paths(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*);;Text Files (*.txt)", options=options)
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', options=options)

        if files:
            self.source_paths.extend(files)
        if folder:
            self.source_paths.append(folder)

        self.update_source_table()

    def update_source_table(self):
        self.source_table.setRowCount(0)
        for path in self.source_paths:
            row_position = self.source_table.rowCount()
            self.source_table.insertRow(row_position)
            self.source_table.setItem(row_position, 0, QTableWidgetItem(path))

    def select_dest_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Destination Folder')
        self.dest_folder = folder

    def add_backup(self):
        time = self.time_edit.time().toString('HH:mm')
        schedule_time = f"{time}"
        selected_days = [day for day, checkbox in self.days_checkboxes.items() if checkbox.isChecked()]
        days_str = ','.join(selected_days)
        send_email = self.send_email_checkbox.isChecked()

        if self.source_paths and self.dest_folder:
            backup_job = BackupJob(
                name="Daily Backup",
                dest_folder=self.dest_folder,
                schedule_time=schedule_time,
                days=days_str,
                send_email=send_email
            )
            for path in self.source_paths:
                backup_job.paths.append(Path(path=path))

            self.session.add(backup_job)
            self.session.commit()

            for day in selected_days:
                if day == 'Monday':
                    schedule.every().monday.at(schedule_time).do(self.start_backup, backup_job.id)
                elif day == 'Tuesday':
                    schedule.every().tuesday.at(schedule_time).do(self.start_backup, backup_job.id)
                elif day == 'Wednesday':
                    schedule.every().wednesday.at(schedule_time).do(self.start_backup, backup_job.id)
                elif day == 'Thursday':
                    schedule.every().thursday.at(schedule_time).do(self.start_backup, backup_job.id)
                elif day == 'Friday':
                    schedule.every().friday.at(schedule_time).do(self.start_backup, backup_job.id)
                elif day == 'Saturday':
                    schedule.every().saturday.at(schedule_time).do(self.start_backup, backup_job.id)
                elif day == 'Sunday':
                    schedule.every().sunday.at(schedule_time).do(self.start_backup, backup_job.id)

            self.status_label.setText(f"Backup scheduled for {days_str} at {schedule_time}")
            print(f"Backup scheduled for {days_str} at {schedule_time}")

    def start_backup(self, backup_job_id):
        backup_job = self.session.query(BackupJob).filter_by(id=backup_job_id).first()
        source_paths = [path.path for path in backup_job.paths]
        self.backup_thread = BackupThread(source_paths, backup_job.dest_folder, backup_job.send_email)
        self.backup_thread.progress.connect(self.update_progress)
        self.backup_thread.current_file.connect(self.update_current_file)
        self.backup_thread.finished.connect(self.backup_finished)
        self.backup_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_current_file(self, file_path):
        self.current_file_label.setText(f'Current file: {file_path}')

    def backup_finished(self, success):
        self.status_label.setText("Status: Backup completed successfully" if success else "Status: Backup failed")
        self.current_file_label.setText('Current file: None')
        if self.send_email_checkbox.isChecked():
            self.send_email(success)

    def send_email(self, success):
        sender_email = EMAIL_USER
        receiver_email = EMAIL_USER
        password = EMAIL_PASSWORD

        message = MIMEMultipart("alternative")
        message["Subject"] = "Backup Completed" if success else "Backup Failed"
        message["From"] = sender_email
        message["To"] = receiver_email

        text = "Your backup has completed successfully." if success else "Your backup has failed."
        part = MIMEText(text, "plain")
        message.attach(part)

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, password)
                server.sendmail(
                    sender_email, receiver_email, message.as_string()
                )
        except Exception as e:
            print(f"Failed to send email: {e}")

    def load_backup_settings(self):
        backup_job = self.session.query(BackupJob).order_by(BackupJob.created_at.desc()).first()
        if backup_job:
            self.dest_folder = backup_job.dest_folder
            schedule_time = backup_job.schedule_time
            hours, minutes = map(int, schedule_time.split(':'))
            self.time_edit.setTime(QTime(hours, minutes))
            self.source_paths = [path.path for path in backup_job.paths]
            self.update_source_table()

            if backup_job.days:
                selected_days = backup_job.days.split(',')
                for day in selected_days:
                    if day in self.days_checkboxes:
                        self.days_checkboxes[day].setChecked(True)

            send_email = backup_job.send_email if backup_job.send_email is not None else False
            self.send_email_checkbox.setChecked(send_email)
        else:
            self.dest_folder = ""
            self.time_edit.setTime(QTime.currentTime())
            self.source_paths = []
            self.update_source_table()
            for checkbox in self.days_checkboxes.values():
                checkbox.setChecked(False)
            self.send_email_checkbox.setChecked(False)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    app = QApplication(sys.argv)
    mainWindow = MainWindow()

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    mainWindow.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
