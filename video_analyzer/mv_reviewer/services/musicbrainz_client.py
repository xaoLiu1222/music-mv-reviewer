"""MusicBrainz client for fetching song metadata (lyricist, composer)."""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# User agent for MusicBrainz API (required)
APP_NAME = "MVReviewer"
APP_VERSION = "0.1.0"
APP_CONTACT = "mv-reviewer@example.com"


class MusicBrainzClient:
    """Client for querying MusicBrainz metadata API."""

    def __init__(self):
        """Initialize MusicBrainz client."""
        self._mb = None

    def _get_mb(self):
        """Lazy load musicbrainzngs to avoid import errors."""
        if self._mb is None:
            try:
                import musicbrainzngs
                musicbrainzngs.set_useragent(APP_NAME, APP_VERSION, APP_CONTACT)
                self._mb = musicbrainzngs
            except ImportError:
                raise ImportError(
                    "musicbrainzngs is required for metadata lookup. "
                    "Install it with: pip install musicbrainzngs"
                )
        return self._mb

    def search_recording(
        self,
        title: str,
        artist: Optional[str] = None,
        limit: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """Search for recordings by title and artist.

        Args:
            title: Song title
            artist: Artist name (optional but recommended)
            limit: Maximum results to return

        Returns:
            List of matching recordings or None
        """
        try:
            mb = self._get_mb()

            query = f'recording:"{title}"'
            if artist:
                query += f' AND artist:"{artist}"'

            result = mb.search_recordings(query=query, limit=limit)

            if not result or 'recording-list' not in result:
                return None

            return result['recording-list']

        except Exception as e:
            logger.error(f"Error searching MusicBrainz: {e}")
            return None

    def get_work_credits(self, recording_id: str) -> Dict[str, List[str]]:
        """Get lyricist and composer credits for a recording.

        Args:
            recording_id: MusicBrainz recording ID

        Returns:
            Dictionary with 'lyricist' and 'composer' lists
        """
        credits = {'lyricist': [], 'composer': []}

        try:
            mb = self._get_mb()

            # Get recording with work relations
            recording = mb.get_recording_by_id(
                recording_id,
                includes=['work-rels', 'artist-credits']
            )

            if not recording or 'recording' not in recording:
                return credits

            rec = recording['recording']

            # Check work relations for credits
            if 'work-relation-list' in rec:
                for work_rel in rec['work-relation-list']:
                    if 'work' in work_rel:
                        work_id = work_rel['work']['id']
                        work_credits = self._get_work_artists(work_id)
                        credits['lyricist'].extend(work_credits.get('lyricist', []))
                        credits['composer'].extend(work_credits.get('composer', []))

            # Remove duplicates
            credits['lyricist'] = list(set(credits['lyricist']))
            credits['composer'] = list(set(credits['composer']))

            return credits

        except Exception as e:
            logger.error(f"Error getting work credits: {e}")
            return credits

    def _get_work_artists(self, work_id: str) -> Dict[str, List[str]]:
        """Get artists associated with a work (lyricist, composer).

        Args:
            work_id: MusicBrainz work ID

        Returns:
            Dictionary with 'lyricist' and 'composer' lists
        """
        credits = {'lyricist': [], 'composer': []}

        try:
            mb = self._get_mb()
            work = mb.get_work_by_id(work_id, includes=['artist-rels'])

            if not work or 'work' not in work:
                return credits

            w = work['work']

            if 'artist-relation-list' in w:
                for rel in w['artist-relation-list']:
                    artist_name = rel.get('artist', {}).get('name', '')
                    rel_type = rel.get('type', '').lower()

                    if rel_type in ['lyricist', 'writer', 'lyrics']:
                        credits['lyricist'].append(artist_name)
                    elif rel_type in ['composer', 'music', 'writer']:
                        credits['composer'].append(artist_name)

            return credits

        except Exception as e:
            logger.debug(f"Error getting work artists: {e}")
            return credits

    def get_song_metadata(
        self,
        title: str,
        artist: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get complete song metadata including lyricist and composer.

        Args:
            title: Song title
            artist: Artist name

        Returns:
            Dictionary with song metadata or None
        """
        recordings = self.search_recording(title, artist)

        if not recordings:
            logger.warning(f"No recordings found for: {title} - {artist}")
            return None

        # Try each recording until we find credits
        for rec in recordings:
            rec_id = rec.get('id')
            if not rec_id:
                continue

            credits = self.get_work_credits(rec_id)

            # If we found any credits, return this result
            if credits['lyricist'] or credits['composer']:
                return {
                    'title': rec.get('title'),
                    'artist': rec.get('artist-credit-phrase', artist),
                    'musicbrainz_id': rec_id,
                    'lyricist': credits['lyricist'],
                    'composer': credits['composer'],
                    'release_date': rec.get('first-release-date'),
                }

        # Return first result even without credits
        first = recordings[0]
        return {
            'title': first.get('title'),
            'artist': first.get('artist-credit-phrase', artist),
            'musicbrainz_id': first.get('id'),
            'lyricist': [],
            'composer': [],
            'release_date': first.get('first-release-date'),
        }
