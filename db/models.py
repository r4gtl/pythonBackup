from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

from datetime import datetime
import logging


# Imposta il livello di log a WARNING
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
# Definizione della base e dell'engine del database
DATABASE_URL = "sqlite:///backup_manager.db"
engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Path(Base):
    __tablename__ = 'paths'
    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=False)
    backup_job_id = Column(Integer, ForeignKey('backup_jobs.id'))


class EmailAddress(Base):
    __tablename__ = 'email_addresses'
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    backup_job_id = Column(Integer, ForeignKey('backup_jobs.id'))
    backup_job = relationship("BackupJob", back_populates="email_addresses")

class BackupJob(Base):
    __tablename__ = 'backup_jobs'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    dest_folder = Column(String, nullable=False)
    schedule_time = Column(String, nullable=False)
    days = Column(String, nullable=False)
    send_email = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_run_date = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)  #

    paths = relationship('Path', backref='backup_job', cascade='all, delete-orphan')
    email_addresses = relationship('EmailAddress', back_populates='backup_job', cascade='all, delete-orphan')


def create_tables():
    Base.metadata.create_all(engine)
