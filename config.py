"""
Configuration file for Databricks PDF Parser App
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the application."""
    
    # Databricks configuration
    DATABRICKS_HOST: Optional[str] = os.getenv('DATABRICKS_HOST')
    DATABRICKS_TOKEN: Optional[str] = os.getenv('DATABRICKS_TOKEN')
    
    # Default warehouse ID (can be overridden in the UI)
    DEFAULT_WAREHOUSE_ID: Optional[str] = os.getenv('DATABRICKS_WAREHOUSE_ID')
    
    # File upload configuration
    MAX_FILE_SIZE_MB: int = 50
    SUPPORTED_FILE_TYPES: list = ['pdf', 'png', 'jpg', 'jpeg']
    
    # DBFS configuration
    DBFS_UPLOAD_PATH: str = "/tmp/document_parser"
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if minimum required configuration is present."""
        return bool(cls.DATABRICKS_HOST and cls.DATABRICKS_TOKEN)
    
    @classmethod
    def get_config_status(cls) -> dict:
        """Get current configuration status."""
        return {
            'databricks_host_configured': bool(cls.DATABRICKS_HOST),
            'databricks_token_configured': bool(cls.DATABRICKS_TOKEN),
            'default_warehouse_configured': bool(cls.DEFAULT_WAREHOUSE_ID),
        }