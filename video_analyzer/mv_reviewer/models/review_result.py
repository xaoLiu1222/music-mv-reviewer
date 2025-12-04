"""Data models for MV review results."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class SongMetadata:
    """Metadata for identified song."""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    lyricist: Optional[List[str]] = None  # 作词
    composer: Optional[List[str]] = None  # 作曲
    release_date: Optional[str] = None
    musicbrainz_id: Optional[str] = None

    def has_creator(self, name: str) -> bool:
        """Check if a creator (lyricist or composer) matches the given name."""
        name_lower = name.lower()
        if self.lyricist:
            for l in self.lyricist:
                if name_lower in l.lower():
                    return True
        if self.composer:
            for c in self.composer:
                if name_lower in c.lower():
                    return True
        return False


@dataclass
class RuleViolation:
    """Represents a single rule violation."""
    rule_id: int
    rule_name: str
    description: str
    confidence: float = 1.0  # 0.0 - 1.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'description': self.description,
            'confidence': self.confidence,
            'details': self.details
        }


@dataclass
class ReviewContext:
    """Context passed to each rule for evaluation."""
    video_path: Path
    audio_path: Optional[Path] = None
    frames: List[Path] = field(default_factory=list)
    song_metadata: Optional[SongMetadata] = None
    video_width: int = 0
    video_height: int = 0
    video_duration: float = 0.0
    fps: float = 0.0

    # Cached analysis results
    _volume_data: Optional[List[float]] = None
    _frame_analyses: Optional[List[Dict[str, Any]]] = None


@dataclass
class ReviewResult:
    """Complete review result for a video."""
    video_path: Path
    is_violation: bool
    violations: List[RuleViolation] = field(default_factory=list)
    song_metadata: Optional[SongMetadata] = None
    review_time: float = 0.0  # seconds
    reviewed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'video_path': str(self.video_path),
            'is_violation': self.is_violation,
            'violations': [v.to_dict() for v in self.violations],
            'song_metadata': {
                'title': self.song_metadata.title if self.song_metadata else None,
                'artist': self.song_metadata.artist if self.song_metadata else None,
                'lyricist': self.song_metadata.lyricist if self.song_metadata else None,
                'composer': self.song_metadata.composer if self.song_metadata else None,
            } if self.song_metadata else None,
            'review_time': self.review_time,
            'reviewed_at': self.reviewed_at,
            'error': self.error
        }

    def get_violated_rule_ids(self) -> List[int]:
        """Get list of violated rule IDs."""
        return [v.rule_id for v in self.violations]
