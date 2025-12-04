"""Rule 3: Volume spike detection."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from .base_rule import BaseRule
from ..models.review_result import RuleViolation, ReviewContext

logger = logging.getLogger(__name__)


class VolumeRule(BaseRule):
    """Rule to detect sudden volume changes (too loud or too quiet).

    Analyzes audio waveform to detect:
    - Sudden volume increases
    - Sudden volume decreases
    - Overall volume too high or too low
    """

    rule_id = 3
    rule_name = "音量突变检测"
    rule_description = "检测音量突然变大或变小"

    # Default thresholds
    DEFAULT_CHANGE_THRESHOLD_DB = 10.0  # dB change to trigger
    DEFAULT_SEGMENT_DURATION_MS = 1000  # Analyze in 1-second segments
    DEFAULT_MIN_VOLUME_DB = -40.0       # Below this is too quiet
    DEFAULT_MAX_VOLUME_DB = -3.0        # Above this is too loud

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize volume rule.

        Args:
            config: Configuration with optional thresholds
        """
        super().__init__(config)
        self.change_threshold_db = self.config.get(
            'change_threshold_db',
            self.DEFAULT_CHANGE_THRESHOLD_DB
        )
        self.segment_duration_ms = self.config.get(
            'segment_duration_ms',
            self.DEFAULT_SEGMENT_DURATION_MS
        )
        self.min_volume_db = self.config.get(
            'min_volume_db',
            self.DEFAULT_MIN_VOLUME_DB
        )
        self.max_volume_db = self.config.get(
            'max_volume_db',
            self.DEFAULT_MAX_VOLUME_DB
        )

    def check(self, context: ReviewContext) -> Optional[RuleViolation]:
        """Check for volume spikes or drops.

        Args:
            context: Review context with video path

        Returns:
            RuleViolation if volume issues detected, None otherwise
        """
        if not self.enabled:
            return None

        try:
            # Extract audio if not already done
            audio_path = self._ensure_audio(context)
            if audio_path is None:
                logger.warning("No audio available for volume analysis")
                return None

            # Analyze volume levels
            volume_data = self._analyze_volume(audio_path)
            if not volume_data:
                return None

            # Check for volume spikes
            spikes = self._detect_volume_spikes(volume_data)

            if spikes:
                spike_times = [f"{s['time']:.1f}s ({s['change']:+.1f}dB)" for s in spikes[:5]]
                return self.create_violation(
                    description=f"检测到音量突变: {len(spikes)}处",
                    confidence=min(len(spikes) / 3, 1.0),
                    details={
                        'spike_count': len(spikes),
                        'spike_times': spike_times,
                        'spikes': spikes[:10],  # First 10 spikes
                        'threshold_db': self.change_threshold_db
                    }
                )

            return None

        except Exception as e:
            logger.error(f"Error in volume rule check: {e}")
            return None

    def _ensure_audio(self, context: ReviewContext) -> Optional[Path]:
        """Ensure audio file exists, extract if needed.

        Args:
            context: Review context

        Returns:
            Path to audio file or None
        """
        if context.audio_path and context.audio_path.exists():
            return context.audio_path

        # Extract audio from video
        temp_dir = context.video_path.parent / ".mv_review_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        audio_path = temp_dir / "audio_for_volume.wav"

        try:
            subprocess.run([
                "ffmpeg", "-i", str(context.video_path),
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                str(audio_path)
            ], check=True, capture_output=True)

            context.audio_path = audio_path
            return audio_path

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            return None

    def _analyze_volume(self, audio_path: Path) -> List[Tuple[float, float]]:
        """Analyze volume levels throughout the audio.

        Args:
            audio_path: Path to audio file

        Returns:
            List of (timestamp, volume_db) tuples
        """
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_wav(str(audio_path))
            duration_ms = len(audio)

            volume_data = []
            for start_ms in range(0, duration_ms, self.segment_duration_ms):
                end_ms = min(start_ms + self.segment_duration_ms, duration_ms)
                segment = audio[start_ms:end_ms]

                # Get dBFS (decibels relative to full scale)
                volume_db = segment.dBFS if segment.dBFS != float('-inf') else -60.0

                timestamp = start_ms / 1000.0
                volume_data.append((timestamp, volume_db))

            return volume_data

        except ImportError:
            logger.error("pydub is required for volume analysis")
            return []
        except Exception as e:
            logger.error(f"Error analyzing volume: {e}")
            return []

    def _detect_volume_spikes(
        self,
        volume_data: List[Tuple[float, float]]
    ) -> List[Dict[str, Any]]:
        """Detect sudden volume changes.

        Args:
            volume_data: List of (timestamp, volume_db) tuples

        Returns:
            List of spike information dictionaries
        """
        spikes = []

        for i in range(1, len(volume_data)):
            prev_time, prev_vol = volume_data[i - 1]
            curr_time, curr_vol = volume_data[i]

            # Skip if either is silence
            if prev_vol < -55 or curr_vol < -55:
                continue

            change = curr_vol - prev_vol

            if abs(change) >= self.change_threshold_db:
                spikes.append({
                    'time': curr_time,
                    'change': change,
                    'from_db': prev_vol,
                    'to_db': curr_vol,
                    'type': 'increase' if change > 0 else 'decrease'
                })

        return spikes
