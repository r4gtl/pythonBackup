import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar, QDialog, QAction
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
import schedule
import time
import threading
import shutil
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from db.models import Session, BackupJob, Path, EmailAddress
from BackupJobDialog import BackupJobDialog

load_dotenv()
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

class BackupThread(QThread):
    progress = pyqtSignal(int)
    current_file = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, source_paths, dest_folder, email_addresses):
        super().__init__()
        self.source_paths = source_paths
        self.dest_folder = dest_folder
        self.email_addresses = email_addresses

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
            raise e

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Backup Manager")
        icon_path = os.path.abspath('icons/backup.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            print("Icon set successfully.")
        else:
            print(f"Icon not found at {icon_path}")

        self.setGeometry(450, 150, 1000, 750)
        self.initUI()
        self.session = Session()
        self.load_backup_jobs()

    def initUI(self):
        self.initToolbar()
        main_layout = QVBoxLayout()  # Main vertical layout

        # Create middle layout (TreeView and Details)
        middle_layout = self.createMiddleLayout()

        # Create bottom layout (ProgressBar and Button)
        bottom_layout = self.createBottomLayout()

        # Add middle and bottom layouts to the main layout
        main_layout.addLayout(middle_layout)
        main_layout.addLayout(bottom_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)



    def initToolbar(self):
        self.tb = self.addToolBar("Tool Bar")
        self.tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        # ToolBar Buttons
        # New Backup Job
        self.addBackupJob = QAction(QIcon('icons/add.png'), "Nuovo Backup Job", self)
        self.addBackupJob.triggered.connect(self.open_backup_job_dialog)
        self.tb.addAction(self.addBackupJob)
        self.tb.addSeparator()

        # Delete Backup Job
        self.deleteBackupJob = QAction(QIcon('icons/delete-folder.png'), "Cancella Backup Job", self)
        # Connect to appropriate slot if required
        self.tb.addAction(self.deleteBackupJob)
        self.tb.addSeparator()

        # Close Application
        self.chiudi = QAction(QIcon('icons/exit.png'), "Esci", self)
        self.chiudi.triggered.connect(self.close)
        self.tb.addAction(self.chiudi)
        self.tb.addSeparator()

    def createMiddleLayout(self):
        middle_layout = QHBoxLayout()

        # Left layout for the tree widget
        left_layout = QVBoxLayout()
        self.tree_widget = QTreeWidget()
        self.tree_widget.setColumnCount(1)
        self.tree_widget.setHeaderLabels(['Backup Jobs'])
        self.tree_widget.itemClicked.connect(self.display_backup_details)
        left_layout.addWidget(self.tree_widget)

        # Right layout for details
        right_layout = QVBoxLayout()
        self.details_label = QLabel('Select a backup job to see details')
        self.details_label.setAlignment(Qt.AlignTop)  # Align the label at the top
        right_layout.addWidget(self.details_label)
        right_layout.addStretch()  # Add stretch to push the label to the top

        # Ensure the left and right layouts have the same width
        self.tree_widget.setFixedWidth(400)
        self.details_label.setFixedWidth(400)

        middle_layout.addLayout(left_layout)
        middle_layout.addLayout(right_layout)

        return middle_layout

    def createBottomLayout(self):
        bottom_layout = QVBoxLayout()
        self.progress_bar = QProgressBar(self)
        bottom_layout.addWidget(self.progress_bar)
        return bottom_layout

    def load_backup_jobs(self):
        self.tree_widget.clear()
        backup_jobs = self.session.query(BackupJob).all()
        for job in backup_jobs:
            item = QTreeWidgetItem([job.name])
            item.setData(0, 1, job.id)
            self.tree_widget.addTopLevelItem(item)

    def display_backup_details(self, item):
        job_id = item.data(0, 1)
        backup_job = self.session.query(BackupJob).get(job_id)
        if backup_job:
            details = f"Name: {backup_job.name}\nDestination: {backup_job.dest_folder}\nTime: {backup_job.schedule_time}\nDays: {backup_job.days}\nSend Email: {backup_job.send_email}\nEmails: {', '.join([email.email for email in backup_job.email_addresses])}"
            self.details_label.setText(details)

    def open_backup_job_dialog(self):
        dialog = BackupJobDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_backup_jobs()

    def start_backup(self, backup_job_id):
        backup_job = self.session.query(BackupJob).get(backup_job_id)
        source_paths = [path.path for path in backup_job.paths]
        email_addresses = [email.email for email in backup_job.email_addresses]
        thread = BackupThread(source_paths, backup_job.dest_folder, email_addresses)
        thread.progress.connect(self.progress_bar.setValue)
        thread.current_file.connect(self.details_label.setText)
        thread.finished.connect(self.backup_finished)
        thread.start()

    def backup_finished(self, success):
        self.details_label.setText("Backup completed successfully." if success else "Backup failed.")
        if success:
            self.send_email(True)
        else:
            self.send_email(False)

    def send_email(self, success):
        sender_email = EMAIL_USER
        password = EMAIL_PASSWORD

        for email_address in self.email_addresses_edit.toPlainText().split(','):
            receiver_email = email_address.strip()

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

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    sys.exit(app.exec_())
