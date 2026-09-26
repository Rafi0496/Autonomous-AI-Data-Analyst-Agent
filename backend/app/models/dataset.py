"""SQLAlchemy database models for Datasets and Dataset Versions."""
import json
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from backend.app.core.database import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="uploaded")
    
    # Paths and JSON metadata for pipeline results
    cleaned_file_path = Column(String(500), nullable=True)
    profile_json = Column(Text, nullable=True)
    cleaning_summary_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def get_profile(self):
        if self.profile_json:
            return json.loads(self.profile_json)
        return None

    def set_profile(self, profile_dict):
        self.profile_json = json.dumps(profile_dict)

    def get_cleaning_summary(self):
        if self.cleaning_summary_json:
            return json.loads(self.cleaning_summary_json)
        return None

    def set_cleaning_summary(self, summary_dict):
        self.cleaning_summary_json = json.dumps(summary_dict)
