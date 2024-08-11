import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar, QDialog, QAction, QPushButton
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, pyqtSlot
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
from db.models import Session, BackupJob, Path, EmailAddress, create_tables
from gui.BackupJobDialog import BackupJobDialog
import datetime

load_dotenv()
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')


'''
class BackupThread(QThread):
    progress = pyqtSignal(int)
    current_file = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, source_paths, dest_folder, email_addresses):
        super().__init__()
        self.source_paths = source_paths
        self.dest_folder = dest_folder
        self.email_addresses = email_addresses
        self._stop_requested = False

    def run(self):
        try:
            self.dest_folder = os.path.join(self.dest_folder, 'backup')
            if not os.path.exists(self.dest_folder):
                os.makedirs(self.dest_folder)

            # Calcolo del numero totale di file da copiare
            total_files = 0
            for source_path in self.source_paths:
                if os.path.isdir(source_path):
                    for _, _, files in os.walk(source_path):
                        total_files += len(files)
                elif os.path.isfile(source_path):
                    total_files += 1

            print(f"Total files to copy: {total_files}")

            copied_files = 0

            for source_path in self.source_paths:
                if os.path.isdir(source_path):
                    # Trattiamo directory
                    for root, _, files in os.walk(source_path):
                        relative_path = os.path.relpath(root, source_path)
                        dest_dir = os.path.join(self.dest_folder, relative_path)

                        if not os.path.exists(dest_dir):
                            os.makedirs(dest_dir)

                        for file in files:
                            if self._stop_requested:
                                self.finished.emit(False)
                                return

                            src_file = os.path.join(root, file)
                            dest_file = os.path.join(dest_dir, file)

                            print(f"Copying file from {src_file} to {dest_file}")
                            if not os.path.exists(dest_file) or os.path.getmtime(src_file) > os.path.getmtime(
                                    dest_file):
                                shutil.copy2(src_file, dest_file)
                                copied_files += 1
                                self.progress.emit(int(copied_files / total_files * 100))
                                self.current_file.emit(src_file)

                elif os.path.isfile(source_path):
                    # Trattiamo file singoli
                    dest_file = os.path.join(self.dest_folder, os.path.basename(source_path))
                    shutil.copy2(source_path, dest_file)
                    copied_files += 1
                    self.progress.emit(int(copied_files / total_files * 100))
                    self.current_file.emit(source_path)

            self.finished.emit(True)
        except Exception as e:
            print(f"Error during backup: {e}")
            self.finished.emit(False)
            raise e
'''

class BackupThread(QThread):
    progress = pyqtSignal(int)
    current_file = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, source_paths, dest_folder, email_addresses):
        super().__init__()
        self.source_paths = source_paths
        self.dest_folder = dest_folder
        self.email_addresses = email_addresses
        self._stop_requested = False

    def run(self):
        try:
            self.dest_folder = os.path.join(self.dest_folder, 'backup')
            if not os.path.exists(self.dest_folder):
                os.makedirs(self.dest_folder)

            total_files = 0
            for source_path in self.source_paths:
                if os.path.isdir(source_path):
                    for _, _, files in os.walk(source_path):
                        total_files += len(files)
                elif os.path.isfile(source_path):
                    total_files += 1

            print(f"Total files to copy: {total_files}")

            copied_files = 0

            for source_path in self.source_paths:
                if os.path.isdir(source_path):
                    for root, _, files in os.walk(source_path):
                        relative_path = os.path.relpath(root, source_path)
                        dest_dir = os.path.join(self.dest_folder, relative_path)

                        if not os.path.exists(dest_dir):
                            os.makedirs(dest_dir)

                        for file in files:
                            if self._stop_requested:
                                self.finished.emit(False)
                                return

                            src_file = os.path.join(root, file)
                            dest_file = os.path.join(dest_dir, file)

                            print(f"Copying file from {src_file} to {dest_file}")
                            if not os.path.exists(dest_file) or os.path.getmtime(src_file) > os.path.getmtime(dest_file):
                                shutil.copy2(src_file, dest_file)
                                copied_files += 1
                                self.progress.emit(int(copied_files / total_files * 100))
                                self.current_file.emit(src_file)

                elif os.path.isfile(source_path):
                    dest_file = os.path.join(self.dest_folder, os.path.basename(source_path))
                    shutil.copy2(source_path, dest_file)
                    copied_files += 1
                    self.progress.emit(int(copied_files / total_files * 100))
                    self.current_file.emit(source_path)

            self.finished.emit(True)
        except Exception as e:
            print(f"Error during backup: {e}")
            self.finished.emit(False)
            raise


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        create_tables()
        self.scheduler_thread_running = True
        self.last_check_time = 0
        self.check_interval = 30  # 1 minuto

        self.current_backup_job_id = None
        self.backup_thread = None
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

        # Flag per il controllo dello stato del thread
        self.scheduler_thread_running = True
        # Avvia il thread dello scheduler
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
        print("Scheduler thread started")

    def initUI(self):
        self.initToolbar()
        main_layout = QVBoxLayout()  # Main vertical layout

        # Create middle layout (TreeView and Details)
        middle_layout = self.createMiddleLayout()

        # Create bottom layout (ProgressBar)
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
        self.tree_widget.itemDoubleClicked.connect(self.edit_backup_job)
        left_layout.addWidget(self.tree_widget)

        # Right layout for details
        right_layout = QVBoxLayout()
        self.details_label = QLabel('Select a backup job to see details')
        self.details_label.setAlignment(Qt.AlignTop)  # Align the label at the top
        right_layout.addWidget(self.details_label)

        # Add start backup button
        self.start_backup_btn = QPushButton('Start Backup Job')
        self.start_backup_btn.clicked.connect(self.start_backup_job)
        right_layout.addWidget(self.start_backup_btn)
        self.refresh_btn = QPushButton('refresh')
        self.refresh_btn.clicked.connect(self.on_backup_job_saved)
        right_layout.addWidget(self.refresh_btn)

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



    def on_backup_job_saved(self, backup_job):
        print("Chiamato")
        # Logica per aggiornare la UI della finestra principale
        print(f"Backup job {backup_job.name} salvato correttamente.")

        # Memorizza l'elemento selezionato
        current_item = self.tree_widget.currentItem()
        print(f"Current item: {current_item}")
        # Aggiorna la lista dei backup jobs
        self.details_label.clear()
        self.update_backup_job_list()


        # Reseleziona l'elemento precedentemente selezionato
        if current_item:
            print(f"current_item: {current_item}")
            items = self.tree_widget.findItems(backup_job.name, Qt.MatchExactly)
            print(f"items: {items}")
            if items:
                item = items[0]
                print(f"item: {item}")
                self.tree_widget.setCurrentItem(item)
                self.display_backup_details(item)

    def update_backup_job_list(self):
        self.load_backup_jobs()


    def load_backup_jobs(self):
        self.tree_widget.clear()
        backup_jobs = self.session.query(BackupJob).all()
        for job in backup_jobs:
            print(f"Sto caricando il Backup job: {job.name}")
            item = QTreeWidgetItem([job.name])
            item.setData(0, 1, job.id)
            self.tree_widget.addTopLevelItem(item)
        print("Backup jobs loaded")

    def display_backup_details(self, item):
        job_id = item.data(0, 1)
        self.current_backup_job_id = job_id
        self.session.expire_all() # Questo forza il refresh degli oggetti dalla sessione
        backup_job = self.session.get(BackupJob, job_id)
        if backup_job:
            details = (f"Nome: {backup_job.name}\nDestinazione: {backup_job.dest_folder}\n"
                       f"Orario: {backup_job.schedule_time}\nGiorni: {backup_job.days}\n"
                       f"Invio Email: {backup_job.send_email}\nEmails: "
                       f"{', '.join([email.email for email in backup_job.email_addresses])}")
            self.details_label.setText(details)

    def edit_backup_job(self, item=None):
        if item is not None:
            job_id = item.data(0, 1)
            backup_job = self.session.get(BackupJob, job_id)
            #backup_job = self.session.query(BackupJob).get(job_id)

            if backup_job:
                dialog = BackupJobDialog(backup_job, parent=self)
                dialog.backup_job_saved.connect(self.on_backup_job_saved)

                if dialog.exec_() == QDialog.Accepted:
                    self.load_backup_jobs()
            else:
                print("Backup job not found.")
        else:
            print("No item provided.")

    def edit_backup_job_elimina(self, item):
        job_id = item.data(0, 1)
        backup_job = self.session.query(BackupJob).get(job_id)
        if backup_job:
            dialog = BackupJobDialog(backup_job, parent=self)  # Pass the backup job to the dialog
            dialog.backup_job_saved.connect(self.on_backup_job_saved)
            print("Connected backup_job_saved signal to on_backup_job_saved method")
            if dialog.exec_() == QDialog.Accepted:
                self.load_backup_jobs()

    def open_backup_job_dialog(self, backup_job=None):
        dialog = BackupJobDialog(backup_job, self)
        print("Attempting to connect backup_job_saved signal to on_backup_job_saved method")
        dialog.backup_job_saved.connect(self.on_backup_job_saved)
        print("Connected backup_job_saved signal to on_backup_job_saved method")
        dialog.exec_()


    def start_backup_job(self):
        if hasattr(self, 'current_backup_job_id'):
            print("Starting backup job...")
            backup_job_id = self.current_backup_job_id
            backup_job = self.session.get(BackupJob, backup_job_id)
            if backup_job:
                source_paths = [path.path for path in backup_job.paths]
                email_addresses = [email.email for email in backup_job.email_addresses]
                print(f"Source paths: {source_paths}")
                print(f"Destination folder: {backup_job.dest_folder}")

                # Stop any existing backup thread
                if self.backup_thread and self.backup_thread.isRunning():
                    self.backup_thread.stop()
                    self.backup_thread.wait()

                # Start a new backup thread
                self.backup_thread = BackupThread(source_paths, backup_job.dest_folder, email_addresses)
                self.backup_thread.progress.connect(self.progress_bar.setValue)
                self.backup_thread.current_file.connect(self.details_label.setText)
                self.backup_thread.finished.connect(self.backup_finished)
                self.backup_thread.start()
            else:
                print("Backup job not found.")
        else:
            print("No backup job selected.")

    def backup_finished(self, success):
        self.details_label.setText("Backup completato con successo." if success else "Backup fallito.")
        if success and self.current_backup_job_id:
            backup_job = self.session.get(BackupJob, self.current_backup_job_id)
            email_addresses = [email.email for email in backup_job.email_addresses] if backup_job else []
            self.send_email(True, email_addresses)
        else:
            self.send_email(False, [])

    def send_email(self, success, email_addresses):
        sender_email = EMAIL_USER
        password = EMAIL_PASSWORD

        for email_address in email_addresses:
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


    def run_scheduler(self):
        print("Scheduler thread running")
        while self.scheduler_thread_running:
            current_time = time.time()
            elapsed_time = current_time - self.last_check_time
            print(f"Current time: {current_time}")
            print(f"Last check time: {self.last_check_time}")
            print(f"Elapsed time: {elapsed_time}")

            if current_time - self.last_check_time >= self.check_interval:
                print("Checking backup jobs")
                for job in self.session.query(BackupJob).all():
                    if self.is_backup_due(job):
                        print(f"Starting backup for job: {job.name}")
                        #self.start_scheduled_backup(job)
                        # Avvia il backup in un nuovo thread
                    thread = BackupThread([path.path for path in job.paths], job.dest_folder, [email.email for email in job.email_addresses])
                    thread.progress.connect(self.progress_bar.setValue)
                    thread.current_file.connect(self.details_label.setText)
                    thread.finished.connect(self.backup_finished)
                    thread.start()
                self.last_check_time = current_time

            schedule.run_pending()
            time.sleep(1)


    '''
        days_mapping = {
            'Lunedì': 'Monday',
            'Martedì': 'Tuesday',
            'Mercoledì': 'Wednesday',
            'Giovedì': 'Thursday',
            'Venerdì': 'Friday',
            'Sabato': 'Saturday',
            'Domenica': 'Sunday'
        }
    '''



    def is_backup_due(self, job):
        now = datetime.datetime.now()

        # Ottieni il giorno della settimana corrente in italiano con la prima lettera maiuscola
        current_day_english = now.strftime("%A")  # Giorno in inglese, e.g., 'Sunday'
        current_day_capitalized = current_day_english.capitalize()  # Giorno con la prima lettera maiuscola

        print(f"Current day in English: {current_day_capitalized}")

        current_time = now.strftime("%H:%M")
        try:
            scheduled_time = datetime.datetime.strptime(job.schedule_time, "%H:%M").strftime("%H:%M")
        except ValueError as e:
            print(f"Error parsing scheduled_time: {e}")
            return False

        # Controlla se il giorno corrente è presente nei giorni pianificati
        scheduled_days = [day.strip() for day in job.days.split(',')]
        print(f"Scheduled days from job: {scheduled_days}")

        # Verifica se il giorno corrente è presente nella lista dei giorni programmati
        is_due_today = current_day_capitalized in scheduled_days
        is_time_matching = current_time == scheduled_time

        print(f"Checking if backup is due: Job={job.name}, Time={scheduled_time}, Day={job.days}")
        print(f"Current day (Capitalized): {current_day_capitalized}, Scheduled days: {scheduled_days}")
        print(f"Is due today? {is_due_today}")
        print(f"Is time matching? {is_time_matching}")

        return is_due_today and is_time_matching


    def start_scheduled_backup(self, job):
        source_paths = [path.path for path in job.paths]
        email_addresses = [email.email for email in job.email_addresses]
        print(f"Starting backup for job: {job.name}")
        thread = BackupThread(source_paths, job.dest_folder, email_addresses)
        thread.progress.connect(self.progress_bar.setValue)
        thread.current_file.connect(self.details_label.setText)
        thread.finished.connect(self.backup_finished)
        thread.start()

    def closeEvent(self, event):
        # Stop the backup thread if it's running
        if self.backup_thread and self.backup_thread.isRunning():
            self.backup_thread.stop()
            self.backup_thread.wait()  # Ensure the thread is fully stopped
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
