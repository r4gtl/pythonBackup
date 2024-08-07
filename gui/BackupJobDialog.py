from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLineEdit, QTimeEdit, QCheckBox, QHBoxLayout, QLabel, QTextEdit, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import QTime
from db.models import Session, BackupJob, Path, EmailAddress

class BackupJobDialog(QDialog):
    def __init__(self, backup_job=None, parent=None):
        super().__init__(parent)
        self.backup_job = backup_job
        self.session = Session()
        self.initUI()

        if backup_job:
            self.load_backup_job()

    def initUI(self):
        self.setWindowTitle('Backup Job')

        layout = QVBoxLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Enter backup job name')
        layout.addWidget(self.name_edit)

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

        self.email_addresses_edit = QTextEdit()
        self.email_addresses_edit.setPlaceholderText("Enter email addresses separated by commas")
        layout.addWidget(self.email_addresses_edit)

        self.save_button = QPushButton('Save Backup Job')
        self.save_button.clicked.connect(self.save_backup_job)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

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

    def load_backup_job(self):
        if self.backup_job:
            self.name_edit.setText(self.backup_job.name)
            self.time_edit.setTime(QTime.fromString(self.backup_job.schedule_time, 'HH:mm'))
            self.source_paths = [path.path for path in self.backup_job.paths]
            self.update_source_table()
            self.dest_folder = self.backup_job.dest_folder

            if self.backup_job.days:
                selected_days = self.backup_job.days.split(',')
                for day in selected_days:
                    if day in self.days_checkboxes:
                        self.days_checkboxes[day].setChecked(True)

            self.send_email_checkbox.setChecked(self.backup_job.send_email)
            email_addresses = [email.email for email in self.backup_job.email_addresses]
            self.email_addresses_edit.setText(','.join(email_addresses))
        else:
            print("No backup job selected.")

    def save_backup_job(self):
        name = self.name_edit.text()
        schedule_time = self.time_edit.time().toString('HH:mm')
        selected_days = [day for day, checkbox in self.days_checkboxes.items() if checkbox.isChecked()]
        days_str = ','.join(selected_days)
        send_email = self.send_email_checkbox.isChecked()
        email_addresses = self.email_addresses_edit.toPlainText().split(',')

        if self.backup_job:
            # Aggiorna l'oggetto esistente
            backup_job = self.session.merge(self.backup_job)

            backup_job.name = name
            backup_job.dest_folder = self.dest_folder
            backup_job.schedule_time = schedule_time
            backup_job.days = days_str
            backup_job.send_email = send_email

            # Pulisci le relazioni esistenti
            backup_job.paths.clear()
            backup_job.email_addresses.clear()

            # Aggiungi i nuovi percorsi e indirizzi email
            for path in self.source_paths:
                backup_job.paths.append(Path(path=path))

            for email in email_addresses:
                backup_job.email_addresses.append(EmailAddress(email=email.strip()))

            self.session.commit()
            self.accept()
        else:
            # Crea un nuovo BackupJob
            backup_job = BackupJob(
                name=name,
                dest_folder=self.dest_folder,
                schedule_time=schedule_time,
                days=days_str,
                send_email=send_email
            )

            for path in self.source_paths:
                backup_job.paths.append(Path(path=path))

            for email in email_addresses:
                backup_job.email_addresses.append(EmailAddress(email=email.strip()))

            self.session.add(backup_job)
            self.session.commit()
            self.accept()




