from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# Definizione della base e dell'engine del database
DATABASE_URL = "sqlite:///backup_manager.db"
engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class BackupJob(Base):
    __tablename__ = 'backup_jobs'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    dest_folder = Column(String, nullable=False)
    schedule_time = Column(String, nullable=False)
    days = Column(Text, nullable=True)
    send_email = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    paths = relationship("Path", back_populates="backup_job")

class Path(Base):
    __tablename__ = 'paths'
    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=False)
    backup_job_id = Column(Integer, ForeignKey('backup_jobs.id'))
    backup_job = relationship("BackupJob", back_populates="paths")

def create_tables():
    Base.metadata.create_all(engine)
