"""Rule 2: Vertical video and black border detection."""

import logging
from typing import Optional, Dict, Any

import cv2
import numpy as np

from .base_rule import BaseRule
from ..models.review_result import RuleViolation, ReviewContext

logger = logging.getLogger(__name__)


class AspectRule(BaseRule):
    """Rule to detect vertical videos and black borders.

    Checks for:
    - Vertical aspect ratio (height > width)
    - Black borders on any side (top, bottom, left, right)
    """

    rule_id = 2
    rule_name = "竖屏/黑边检测"
    rule_description = "检测竖屏视频或带有黑边的视频"

    # Default thresholds
    DEFAULT_BLACK_THRESHOLD = 15  # Pixel value below this is considered black
    DEFAULT_BORDER_RATIO = 0.05   # Minimum border ratio to trigger (5%)

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize aspect rule.

        Args:
            config: Configuration with optional thresholds
        """
        super().__init__(config)
        self.black_threshold = self.config.get(
            'black_threshold',
            self.DEFAULT_BLACK_THRESHOLD
        )
        self.border_ratio = self.config.get(
            'border_ratio',
            self.DEFAULT_BORDER_RATIO
        )

    def check(self, context: ReviewContext) -> Optional[RuleViolation]:
        """Check for vertical video or black borders.

        Args:
            context: Review context with video path

        Returns:
            RuleViolation if vertical or has black borders, None otherwise
        """
        if not self.enabled:
            return None

        try:
            # Open video to get dimensions and first frame
            cap = cv2.VideoCapture(str(context.video_path))
            if not cap.isOpened():
                logger.error(f"Could not open video: {context.video_path}")
                return None

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Update context with video dimensions
            context.video_width = width
            context.video_height = height

            # Check 1: Vertical video
            if height > width:
                cap.release()
                return self.create_violation(
                    description=f"检测到竖屏视频 (宽:{width} x 高:{height})",
                    confidence=1.0,
                    details={
                        'type': 'vertical',
                        'width': width,
                        'height': height,
                        'aspect_ratio': width / height
                    }
                )

            # Read first frame for black border detection
            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                logger.error("Could not read video frame")
                return None

            # Check 2: Black borders
            border_info = self._detect_black_borders(frame)

            if border_info['has_borders']:
                return self.create_violation(
                    description=f"检测到黑边: {', '.join(border_info['border_sides'])}",
                    confidence=border_info['confidence'],
                    details={
                        'type': 'black_borders',
                        'border_sides': border_info['border_sides'],
                        'border_ratios': border_info['border_ratios'],
                        'width': width,
                        'height': height
                    }
                )

            return None

        except Exception as e:
            logger.error(f"Error in aspect rule check: {e}")
            return None

    def _detect_black_borders(self, frame: np.ndarray) -> Dict[str, Any]:
        """Detect black borders on frame edges.

        Args:
            frame: Video frame as numpy array

        Returns:
            Dictionary with border detection results
        """
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        border_sides = []
        border_ratios = {}

        # Check top border
        top_ratio = self._get_border_ratio(gray, 'top')
        if top_ratio >= self.border_ratio:
            border_sides.append('上')
            border_ratios['top'] = top_ratio

        # Check bottom border
        bottom_ratio = self._get_border_ratio(gray, 'bottom')
        if bottom_ratio >= self.border_ratio:
            border_sides.append('下')
            border_ratios['bottom'] = bottom_ratio

        # Check left border
        left_ratio = self._get_border_ratio(gray, 'left')
        if left_ratio >= self.border_ratio:
            border_sides.append('左')
            border_ratios['left'] = left_ratio

        # Check right border
        right_ratio = self._get_border_ratio(gray, 'right')
        if right_ratio >= self.border_ratio:
            border_sides.append('右')
            border_ratios['right'] = right_ratio

        has_borders = len(border_sides) > 0
        confidence = max(border_ratios.values()) if border_ratios else 0.0

        return {
            'has_borders': has_borders,
            'border_sides': border_sides,
            'border_ratios': border_ratios,
            'confidence': min(confidence * 10, 1.0)  # Scale to 0-1
        }

    def _get_border_ratio(self, gray: np.ndarray, side: str) -> float:
        """Calculate the ratio of black pixels on a specific side.

        Args:
            gray: Grayscale frame
            side: 'top', 'bottom', 'left', or 'right'

        Returns:
            Ratio of frame height/width that is black border
        """
        height, width = gray.shape

        if side == 'top':
            for i in range(height // 2):
                row = gray[i, :]
                if np.mean(row) > self.black_threshold:
                    return i / height
            return 0.5

        elif side == 'bottom':
            for i in range(height - 1, height // 2, -1):
                row = gray[i, :]
                if np.mean(row) > self.black_threshold:
                    return (height - 1 - i) / height
            return 0.5

        elif side == 'left':
            for i in range(width // 2):
                col = gray[:, i]
                if np.mean(col) > self.black_threshold:
                    return i / width
            return 0.5

        elif side == 'right':
            for i in range(width - 1, width // 2, -1):
                col = gray[:, i]
                if np.mean(col) > self.black_threshold:
                    return (width - 1 - i) / width
            return 0.5

        return 0.0
