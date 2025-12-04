"""Main MV Reviewer class that orchestrates all review rules."""

import logging
import shutil
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models.review_result import ReviewResult, ReviewContext, RuleViolation
from .rules.base_rule import BaseRule
from .rules.metadata_rule import MetadataRule
from .rules.aspect_rule import AspectRule
from .rules.volume_rule import VolumeRule
from .rules.content_rule import ContentRule

logger = logging.getLogger(__name__)


class MVReviewer:
    """Main class for reviewing music videos against configured rules."""

    # Supported video extensions
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm_client: Any = None,
        model: str = "llama3.2-vision",
        enabled_rules: Optional[List[int]] = None
    ):
        """Initialize MV Reviewer.

        Args:
            config: Configuration dictionary
            llm_client: LLM client for content analysis
            model: Model name for LLM
            enabled_rules: List of rule IDs to enable (1-7), None for all
        """
        self.config = config or {}
        self.llm_client = llm_client
        self.model = model
        self.enabled_rules = enabled_rules

        # Initialize rules
        self.rules = self._init_rules()

    def _init_rules(self) -> List[BaseRule]:
        """Initialize all review rules.

        Returns:
            List of initialized rule instances
        """
        rules_config = self.config.get('rules', {})

        all_rules = [
            MetadataRule(rules_config.get('metadata', {})),
            AspectRule(rules_config.get('aspect', {})),
            VolumeRule(rules_config.get('volume', {})),
            ContentRule(
                rules_config.get('content', {}),
                llm_client=self.llm_client,
                model=self.model
            ),
        ]

        # Filter by enabled rules if specified
        if self.enabled_rules:
            # Content rule covers 4-7, so include it if any of 4-7 is enabled
            content_rule_ids = {4, 5, 6, 7}
            enabled_set = set(self.enabled_rules)

            filtered_rules = []
            for rule in all_rules:
                if rule.rule_id in enabled_set:
                    filtered_rules.append(rule)
                elif rule.rule_id == 4 and enabled_set & content_rule_ids:
                    # Content rule covers 4-7
                    filtered_rules.append(rule)

            return filtered_rules

        return all_rules

    def review(self, video_path: Path) -> ReviewResult:
        """Review a single video against all enabled rules.

        Args:
            video_path: Path to video file

        Returns:
            ReviewResult with all violations found
        """
        start_time = time.time()
        video_path = Path(video_path)

        if not video_path.exists():
            return ReviewResult(
                video_path=video_path,
                is_violation=False,
                error=f"Video file not found: {video_path}"
            )

        logger.info(f"Reviewing: {video_path.name}")

        # Build review context
        context = ReviewContext(video_path=video_path)

        # Run all rules
        violations: List[RuleViolation] = []

        for rule in self.rules:
            try:
                logger.debug(f"Running rule: {rule.rule_name}")
                violation = rule.check(context)

                if violation:
                    violations.append(violation)
                    logger.info(f"  [VIOLATION] Rule {rule.rule_id}: {violation.description}")

            except Exception as e:
                logger.error(f"Error running rule {rule.rule_name}: {e}")

        # Cleanup temp files
        self._cleanup_temp(video_path)

        review_time = time.time() - start_time

        return ReviewResult(
            video_path=video_path,
            is_violation=len(violations) > 0,
            violations=violations,
            song_metadata=context.song_metadata,
            review_time=review_time
        )

    def review_batch(
        self,
        directory: Path,
        violation_dir: Optional[Path] = None,
        recursive: bool = False,
        progress_callback: Optional[callable] = None
    ) -> List[ReviewResult]:
        """Review all videos in a directory.

        Args:
            directory: Directory containing videos
            violation_dir: Directory to move violations to
            recursive: Whether to search subdirectories
            progress_callback: Optional callback(current, total, video_name, result)

        Returns:
            List of ReviewResult for all videos
        """
        directory = Path(directory)
        if not directory.is_dir():
            logger.error(f"Not a directory: {directory}")
            return []

        # Find all video files
        if recursive:
            video_files = [
                f for f in directory.rglob('*')
                if f.suffix.lower() in self.VIDEO_EXTENSIONS
            ]
        else:
            video_files = [
                f for f in directory.iterdir()
                if f.is_file() and f.suffix.lower() in self.VIDEO_EXTENSIONS
            ]

        # Sort for consistent ordering
        video_files.sort()

        logger.info(f"Found {len(video_files)} video files to review")

        results = []
        total = len(video_files)

        for i, video_path in enumerate(video_files, 1):
            logger.info(f"[{i}/{total}] Processing: {video_path.name}")

            result = self.review(video_path)
            results.append(result)

            # Move violation to violation directory
            if result.is_violation and violation_dir:
                self._move_violation(video_path, violation_dir)

            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(i, total, video_path.name, result)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

        return results

    def _move_violation(self, video_path: Path, violation_dir: Path) -> bool:
        """Move a violating video to the violation directory.

        Args:
            video_path: Path to video file
            violation_dir: Target directory

        Returns:
            True if moved successfully
        """
        try:
            violation_dir = Path(violation_dir)
            violation_dir.mkdir(parents=True, exist_ok=True)

            dest_path = violation_dir / video_path.name

            # Handle duplicate names
            if dest_path.exists():
                stem = video_path.stem
                suffix = video_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = violation_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(video_path), str(dest_path))
            logger.info(f"  Moved to: {dest_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to move violation: {e}")
            return False

    def _cleanup_temp(self, video_path: Path):
        """Clean up temporary files created during review.

        Args:
            video_path: Path to video file
        """
        temp_dir = video_path.parent / ".mv_review_temp"
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")

    @staticmethod
    def generate_report(results: List[ReviewResult]) -> Dict[str, Any]:
        """Generate a summary report from review results.

        Args:
            results: List of review results

        Returns:
            Report dictionary
        """
        total = len(results)
        violations = [r for r in results if r.is_violation]
        passed = [r for r in results if not r.is_violation and not r.error]
        errors = [r for r in results if r.error]

        total_time = sum(r.review_time for r in results)

        # Count violations by rule
        rule_counts: Dict[int, int] = {}
        for result in violations:
            for v in result.violations:
                rule_counts[v.rule_id] = rule_counts.get(v.rule_id, 0) + 1

        return {
            'summary': {
                'total': total,
                'passed': len(passed),
                'violated': len(violations),
                'errors': len(errors),
                'total_time_seconds': round(total_time, 2),
                'average_time_seconds': round(total_time / total, 2) if total > 0 else 0
            },
            'violations_by_rule': rule_counts,
            'violations': [r.to_dict() for r in violations],
            'errors': [{'video': str(r.video_path), 'error': r.error} for r in errors]
        }
