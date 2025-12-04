"""Base class for all review rules."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

from ..models.review_result import RuleViolation, ReviewContext

logger = logging.getLogger(__name__)


class BaseRule(ABC):
    """Abstract base class for review rules."""

    rule_id: int = 0
    rule_name: str = "Base Rule"
    rule_description: str = ""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize rule with optional configuration.

        Args:
            config: Rule-specific configuration dictionary
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)

    @abstractmethod
    def check(self, context: ReviewContext) -> Optional[RuleViolation]:
        """Check if the video violates this rule.

        Args:
            context: Review context containing video information

        Returns:
            RuleViolation if violated, None if passed
        """
        pass

    def create_violation(
        self,
        description: str,
        confidence: float = 1.0,
        details: Optional[Dict[str, Any]] = None
    ) -> RuleViolation:
        """Helper to create a violation for this rule.

        Args:
            description: Human-readable violation description
            confidence: Confidence score 0.0-1.0
            details: Additional details dictionary

        Returns:
            RuleViolation instance
        """
        return RuleViolation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            description=description,
            confidence=confidence,
            details=details or {}
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.rule_id}, enabled={self.enabled})>"
