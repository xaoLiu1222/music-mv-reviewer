"""Rule 1: Blocked lyricist/composer detection."""

import logging
from typing import Optional, List, Dict, Any

from .base_rule import BaseRule
from ..models.review_result import RuleViolation, ReviewContext, SongMetadata
from ..services.shazam_client import ShazamClient
from ..services.musicbrainz_client import MusicBrainzClient

logger = logging.getLogger(__name__)


class MetadataRule(BaseRule):
    """Rule to detect blocked lyricists or composers.

    This rule identifies the song using Shazam, then queries MusicBrainz
    for lyricist/composer information to check against a blocklist.
    """

    rule_id = 1
    rule_name = "作词作曲检测"
    rule_description = "检测作词或作曲是否在黑名单中"

    # Default blocked creators
    DEFAULT_BLOCKED_CREATORS = ["林夕"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize metadata rule.

        Args:
            config: Configuration with optional 'blocked_creators' list
        """
        super().__init__(config)
        self.blocked_creators = self.config.get(
            'blocked_creators',
            self.DEFAULT_BLOCKED_CREATORS
        )
        self.shazam_client = ShazamClient()
        self.musicbrainz_client = MusicBrainzClient()

    def check(self, context: ReviewContext) -> Optional[RuleViolation]:
        """Check if song's lyricist/composer is in blocklist.

        Args:
            context: Review context with video path

        Returns:
            RuleViolation if blocked creator found, None otherwise
        """
        if not self.enabled:
            return None

        try:
            # Get or identify song metadata
            metadata = self._get_song_metadata(context)

            if metadata is None:
                logger.warning(f"Could not identify song for {context.video_path}")
                return None

            # Store metadata in context for other rules
            context.song_metadata = metadata

            # Check against blocklist
            for blocked_name in self.blocked_creators:
                if metadata.has_creator(blocked_name):
                    matched_roles = self._get_matched_roles(metadata, blocked_name)
                    return self.create_violation(
                        description=f"检测到黑名单创作者: {blocked_name} ({', '.join(matched_roles)})",
                        confidence=1.0,
                        details={
                            'blocked_creator': blocked_name,
                            'matched_roles': matched_roles,
                            'song_title': metadata.title,
                            'song_artist': metadata.artist,
                            'lyricist': metadata.lyricist,
                            'composer': metadata.composer,
                        }
                    )

            return None

        except Exception as e:
            logger.error(f"Error in metadata rule check: {e}")
            return None

    def _get_song_metadata(self, context: ReviewContext) -> Optional[SongMetadata]:
        """Get song metadata, using cached value if available.

        Args:
            context: Review context

        Returns:
            SongMetadata or None
        """
        # Return cached metadata if available
        if context.song_metadata is not None:
            return context.song_metadata

        # Step 1: Identify song using Shazam
        temp_dir = context.video_path.parent / ".mv_review_temp"
        shazam_result = self.shazam_client.identify_from_video(
            context.video_path,
            temp_dir
        )

        if not shazam_result:
            logger.warning("Shazam could not identify the song")
            return None

        title = shazam_result.get('title')
        artist = shazam_result.get('artist')

        logger.info(f"Shazam identified: {title} - {artist}")

        # Step 2: Query MusicBrainz for lyricist/composer
        mb_result = self.musicbrainz_client.get_song_metadata(title, artist)

        if mb_result:
            return SongMetadata(
                title=mb_result.get('title', title),
                artist=mb_result.get('artist', artist),
                lyricist=mb_result.get('lyricist', []),
                composer=mb_result.get('composer', []),
                musicbrainz_id=mb_result.get('musicbrainz_id'),
                release_date=mb_result.get('release_date'),
            )
        else:
            # Return basic metadata from Shazam
            return SongMetadata(
                title=title,
                artist=artist,
                lyricist=[],
                composer=[],
            )

    def _get_matched_roles(self, metadata: SongMetadata, name: str) -> List[str]:
        """Get list of roles where the name was matched.

        Args:
            metadata: Song metadata
            name: Creator name to check

        Returns:
            List of matched roles (e.g., ['作词', '作曲'])
        """
        roles = []
        name_lower = name.lower()

        if metadata.lyricist:
            for l in metadata.lyricist:
                if name_lower in l.lower():
                    roles.append('作词')
                    break

        if metadata.composer:
            for c in metadata.composer:
                if name_lower in c.lower():
                    roles.append('作曲')
                    break

        return roles
