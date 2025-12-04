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
    - Black borders: top+bottom >= 40% OR left+right >= 40%
    """

    rule_id = 2
    rule_name = "竖屏/黑边检测"
    rule_description = "检测竖屏视频或黑边占比>=40%的视频"

    # Default thresholds
    DEFAULT_BLACK_THRESHOLD = 15      # Pixel value below this is considered black
    DEFAULT_TOTAL_BORDER_RATIO = 0.40 # Total border ratio threshold (40%)

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
        self.total_border_ratio = self.config.get(
            'total_border_ratio',
            self.DEFAULT_TOTAL_BORDER_RATIO
        )

    def check(self, context: ReviewContext) -> Optional[RuleViolation]:
        """Check for vertical video or black borders.

        Args:
            context: Review context with video path

        Returns:
            RuleViolation if vertical or has excessive black borders, None otherwise
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

            # Check 2: Black borders (total ratio >= 40%)
            border_info = self._detect_black_borders(frame)

            if border_info['has_violation']:
                return self.create_violation(
                    description=border_info['description'],
                    confidence=border_info['confidence'],
                    details={
                        'type': 'black_borders',
                        'violation_type': border_info['violation_type'],
                        'top_ratio': border_info['top_ratio'],
                        'bottom_ratio': border_info['bottom_ratio'],
                        'left_ratio': border_info['left_ratio'],
                        'right_ratio': border_info['right_ratio'],
                        'vertical_total': border_info['vertical_total'],
                        'horizontal_total': border_info['horizontal_total'],
                        'threshold': self.total_border_ratio,
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

        New logic: Violation if top+bottom >= 40% OR left+right >= 40%

        Args:
            frame: Video frame as numpy array

        Returns:
            Dictionary with border detection results
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Get individual border ratios
        top_ratio = self._get_border_ratio(gray, 'top')
        bottom_ratio = self._get_border_ratio(gray, 'bottom')
        left_ratio = self._get_border_ratio(gray, 'left')
        right_ratio = self._get_border_ratio(gray, 'right')

        # Calculate totals
        vertical_total = top_ratio + bottom_ratio    # 上下黑边总和
        horizontal_total = left_ratio + right_ratio  # 左右黑边总和

        # Check if violation (>= 40%)
        has_violation = False
        violation_type = None
        description = ""

        if vertical_total >= self.total_border_ratio:
            has_violation = True
            violation_type = 'vertical_borders'
            description = f"上下黑边占比过高: {vertical_total*100:.1f}% (阈值: {self.total_border_ratio*100:.0f}%)"

        if horizontal_total >= self.total_border_ratio:
            has_violation = True
            if violation_type:
                violation_type = 'both_borders'
                description = f"上下黑边: {vertical_total*100:.1f}%, 左右黑边: {horizontal_total*100:.1f}% (阈值: {self.total_border_ratio*100:.0f}%)"
            else:
                violation_type = 'horizontal_borders'
                description = f"左右黑边占比过高: {horizontal_total*100:.1f}% (阈值: {self.total_border_ratio*100:.0f}%)"

        # Calculate confidence based on how much it exceeds threshold
        confidence = 0.0
        if has_violation:
            max_ratio = max(vertical_total, horizontal_total)
            confidence = min((max_ratio / self.total_border_ratio), 1.0)

        return {
            'has_violation': has_violation,
            'violation_type': violation_type,
            'description': description,
            'top_ratio': top_ratio,
            'bottom_ratio': bottom_ratio,
            'left_ratio': left_ratio,
            'right_ratio': right_ratio,
            'vertical_total': vertical_total,
            'horizontal_total': horizontal_total,
            'confidence': confidence
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
