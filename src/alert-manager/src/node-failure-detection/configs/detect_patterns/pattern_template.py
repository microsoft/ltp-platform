"""
Base Pattern Class Template

All detection patterns should inherit from this base class.
This provides a standard interface. Patterns must register themselves explicitly.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class Pattern(ABC):
    """
    Base class for all detection patterns.
    
    Patterns should inherit from this class and implement the required methods.
    Patterns must register themselves explicitly by calling register_pattern().
    """
    
    @property
    @abstractmethod
    def pattern_id(self) -> str:
        """Unique identifier for this pattern"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this pattern detects"""
        pass
    
    @property
    @abstractmethod
    def required_data(self) -> List[str]:
        """List of required data sources (e.g., ['metrics:gpu_temp', 'logs:dmesg'])"""
        pass
    
    @property
    def schedule(self) -> Optional[str]:
        """
        Schedule for automatic analysis (e.g., '30s', '5m', '1h').
        Return None for event-driven patterns.
        """
        return None
    
    @property
    def data_spec(self) -> Dict[str, Any]:
        """
        Data collection specification for this pattern.
        Defines how to collect the required data.
        """
        return {}
    
    @abstractmethod
    def analyze(self, data: Dict[str, Any], raw_result_key: str) -> Dict[str, Any]:
        """
        Analyze the collected data and return detection results.
        
        Args:
            data: Collected monitoring data
            raw_result_key: Key/identifier for the raw monitoring result
            
        Returns:
            Analysis result dict with standardized format:
            {
                "pattern_id": str,
                "analysis_timestamp": str,
                "status": str,  # "healthy", "issue_detected", "warning"
                "affected_nodes": List[str],
                "action": str,  # "none", "alert", "cordon", "drain"
                "reason": str,
                "evidence": Dict[str, Any],
                "confidence": float,  # 0.0 to 1.0
                "raw_result_key": str
            }
        """
        pass
    
    def __str__(self):
        """String representation of the pattern"""
        schedule_info = f"every {self.schedule}" if self.schedule else "event-driven"
        return f"Pattern({self.pattern_id}, {schedule_info})"
    
    def __repr__(self):
        return self.__str__()


class ScheduledPattern(Pattern):
    """
    Base class for patterns that run on a schedule.
    Automatically sets up scheduling properties.
    """
    
    @property
    @abstractmethod
    def schedule(self) -> str:
        """Schedule for automatic analysis (e.g., '30s', '5m', '1h')"""
        pass


class EventDrivenPattern(Pattern):
    """
    Base class for patterns that are triggered by events.
    These patterns run on-demand when investigations are requested.
    """
    
    @property
    def schedule(self) -> None:
        """Event-driven patterns have no schedule"""
        return None 