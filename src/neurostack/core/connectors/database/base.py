"""
Base Connector Class

This module provides the abstract base class for all data storage connectors.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """
    Abstract base class for all data storage connectors.
    
    All connectors must implement the methods defined in this class.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the connector with configuration.
        
        Args:
            config: Dictionary containing connection configuration parameters
        """
        self.config = config
        self.connection = None
        self._is_connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the data storage system.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """
        Close the connection to the data storage system.
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if the connector is currently connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a query on the data storage system.
        
        Args:
            query: Query string to execute
            params: Optional parameters for the query
            
        Returns:
            Query results
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Perform a health check on the connection.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        pass
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def __repr__(self) -> str:
        """String representation of the connector."""
        return f"{self.__class__.__name__}(connected={self._is_connected})"

