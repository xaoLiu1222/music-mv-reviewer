"""Rules 4-7: Content review using Vision LLM."""

import json
import logging
from typing import Optional, List, Dict, Any

from .base_rule import BaseRule
from ..models.review_result import RuleViolation, ReviewContext

logger = logging.getLogger(__name__)


class ContentRule(BaseRule):
    """Combined rule for content review using Vision LLM.

    Checks for:
    - Rule 4: Exposure/inappropriate content (暴露/导向问题)
    - Rule 5: Landscape-only background (纯风景背景)
    - Rule 6: Advertisement content (广告内容)
    - Rule 7: Drug use scenes (吸毒画面)
    """

    rule_id = 4  # Primary rule ID (covers 4-7)
    rule_name = "内容审核"
    rule_description = "检测暴露、导向问题、纯风景、广告、吸毒等内容"

    # Content check types with their rule IDs
    CONTENT_CHECKS = {
        'exposure': {'rule_id': 4, 'name': '暴露/导向问题'},
        'inappropriate': {'rule_id': 4, 'name': '导向问题'},
        'landscape_only': {'rule_id': 5, 'name': '纯风景背景'},
        'advertisement': {'rule_id': 6, 'name': '广告内容'},
        'drug_use': {'rule_id': 7, 'name': '吸毒画面'},
    }

    DEFAULT_CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm_client: Any = None,
        model: str = "llama3.2-vision"
    ):
        """Initialize content rule.

        Args:
            config: Configuration dictionary
            llm_client: LLM client for vision analysis
            model: Model name to use
        """
        super().__init__(config)
        self.llm_client = llm_client
        self.model = model
        self.confidence_threshold = self.config.get(
            'confidence_threshold',
            self.DEFAULT_CONFIDENCE_THRESHOLD
        )
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load the content review prompt template."""
        return """你是一个专业的视频内容审核员。请仔细分析这个视频帧，检查是否存在以下违规内容：

1. 暴露内容 (exposure)：裸露、性暗示、不雅动作、低俗色情
2. 导向问题 (inappropriate)：政治敏感内容、暴力血腥、恐怖画面、不当价值观
3. 纯风景背景 (landscape_only)：画面仅有自然风景（山水、天空、海洋、森林等），完全没有人物、歌手或其他主体内容
4. 广告内容 (advertisement)：商品展示、品牌logo、促销信息、二维码、购物链接
5. 吸毒画面 (drug_use)：吸食毒品、注射器、毒品相关物品、吸毒动作

请以严格的JSON格式返回检测结果，不要添加任何其他文字：
{
  "exposure": {"detected": false, "confidence": 0.0, "description": ""},
  "inappropriate": {"detected": false, "confidence": 0.0, "description": ""},
  "landscape_only": {"detected": false, "confidence": 0.0, "description": ""},
  "advertisement": {"detected": false, "confidence": 0.0, "description": ""},
  "drug_use": {"detected": false, "confidence": 0.0, "description": ""}
}

注意：
- detected: 是否检测到该类型内容 (true/false)
- confidence: 置信度 (0.0-1.0)
- description: 简短描述检测到的内容（中文）
- 如果画面正常，所有detected都应为false"""

    def check(self, context: ReviewContext) -> Optional[RuleViolation]:
        """Check for content violations using Vision LLM.

        Args:
            context: Review context with frames

        Returns:
            RuleViolation if content issues detected, None otherwise
        """
        if not self.enabled:
            return None

        if self.llm_client is None:
            logger.warning("No LLM client configured for content review")
            return None

        try:
            # Get frames to analyze
            frames = self._get_frames_to_analyze(context)
            if not frames:
                logger.warning("No frames available for content analysis")
                return None

            # Analyze each frame
            all_violations = []
            for frame_path in frames:
                frame_result = self._analyze_frame(frame_path)
                if frame_result:
                    all_violations.extend(frame_result)

            # Return first violation found (most severe)
            if all_violations:
                # Sort by confidence and return highest
                all_violations.sort(key=lambda x: x.confidence, reverse=True)
                return all_violations[0]

            return None

        except Exception as e:
            logger.error(f"Error in content rule check: {e}")
            return None

    def _get_frames_to_analyze(self, context: ReviewContext) -> List[str]:
        """Get list of frame paths to analyze.

        Args:
            context: Review context

        Returns:
            List of frame file paths
        """
        if context.frames:
            # Use pre-extracted frames
            return [str(f) for f in context.frames[:5]]  # Analyze up to 5 frames

        # Extract frames from video
        import cv2
        from pathlib import Path

        temp_dir = context.video_path.parent / ".mv_review_temp" / "frames"
        temp_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(context.video_path))
        if not cap.isOpened():
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0

        # Sample 5 frames evenly distributed
        frame_paths = []
        sample_points = [0.1, 0.3, 0.5, 0.7, 0.9]  # 10%, 30%, 50%, 70%, 90%

        for i, point in enumerate(sample_points):
            frame_num = int(total_frames * point)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()

            if ret:
                frame_path = temp_dir / f"content_frame_{i}.jpg"
                cv2.imwrite(str(frame_path), frame)
                frame_paths.append(str(frame_path))

        cap.release()
        context.frames = [Path(p) for p in frame_paths]
        return frame_paths

    def _analyze_frame(self, frame_path: str) -> List[RuleViolation]:
        """Analyze a single frame for content violations.

        Args:
            frame_path: Path to frame image

        Returns:
            List of violations found in this frame
        """
        violations = []

        try:
            # Call LLM with frame
            response = self.llm_client.generate(
                prompt=self.prompt_template,
                image_path=frame_path,
                model=self.model,
                temperature=0.1,
                num_predict=500
            )

            response_text = response.get('response', '')

            # Parse JSON response
            result = self._parse_llm_response(response_text)
            if not result:
                return violations

            # Check each content type
            for check_type, check_info in self.CONTENT_CHECKS.items():
                if check_type in result:
                    check_result = result[check_type]
                    if (check_result.get('detected', False) and
                        check_result.get('confidence', 0) >= self.confidence_threshold):

                        violation = RuleViolation(
                            rule_id=check_info['rule_id'],
                            rule_name=check_info['name'],
                            description=check_result.get('description', f'检测到{check_info["name"]}'),
                            confidence=check_result.get('confidence', 0.8),
                            details={
                                'check_type': check_type,
                                'frame_path': frame_path,
                                'raw_result': check_result
                            }
                        )
                        violations.append(violation)

        except Exception as e:
            logger.error(f"Error analyzing frame {frame_path}: {e}")

        return violations

    def _parse_llm_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response to extract JSON result.

        Args:
            response_text: Raw LLM response

        Returns:
            Parsed dictionary or None
        """
        try:
            # Try to find JSON in response
            text = response_text.strip()

            # Find JSON block
            start_idx = text.find('{')
            end_idx = text.rfind('}')

            if start_idx != -1 and end_idx != -1:
                json_str = text[start_idx:end_idx + 1]
                return json.loads(json_str)

            return None

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return None
