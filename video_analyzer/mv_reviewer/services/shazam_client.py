"""Shazam audio fingerprint client for song identification."""

import asyncio
import logging
import platform
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Windows asyncio compatibility
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class ShazamClient:
    """Client for identifying songs using Shazam API."""

    def __init__(self):
        """Initialize Shazam client."""
        self._shazam = None

    def _get_shazam(self):
        """Lazy load shazamio to avoid import errors if not installed."""
        if self._shazam is None:
            try:
                from shazamio import Shazam
                self._shazam = Shazam()
            except ImportError:
                raise ImportError(
                    "shazamio is required for song identification. "
                    "Install it with: pip install shazamio"
                )
        return self._shazam

    async def _identify_async(self, audio_path: Path) -> Optional[Dict[str, Any]]:
        """Async method to identify song from audio file.

        Args:
            audio_path: Path to audio file (wav, mp3, etc.)

        Returns:
            Dictionary with song info or None if not identified
        """
        try:
            shazam = self._get_shazam()
            result = await shazam.recognize(str(audio_path))

            if not result or 'track' not in result:
                logger.warning(f"Could not identify song from {audio_path}")
                return None

            track = result['track']
            return {
                'title': track.get('title'),
                'artist': track.get('subtitle'),
                'album': track.get('sections', [{}])[0].get('metadata', [{}])[0].get('text')
                         if track.get('sections') else None,
                'shazam_key': track.get('key'),
                'genre': track.get('genres', {}).get('primary'),
            }

        except Exception as e:
            logger.error(f"Error identifying song: {e}")
            return None

    def identify(self, audio_path: Path) -> Optional[Dict[str, Any]]:
        """Identify song from audio file (sync wrapper).

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with song info or None if not identified
        """
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        try:
            # Run async method in event loop (Windows compatible)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # If already in async context, create new loop in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._identify_async(audio_path))
                    return future.result(timeout=60)
            else:
                # No running loop, safe to use asyncio.run
                return asyncio.run(self._identify_async(audio_path))

        except Exception as e:
            logger.error(f"Error in song identification: {e}")
            return None

    def identify_from_video(self, video_path: Path, temp_dir: Path) -> Optional[Dict[str, Any]]:
        """Extract audio from video and identify song.

        Args:
            video_path: Path to video file
            temp_dir: Directory for temporary audio file

        Returns:
            Dictionary with song info or None
        """
        import subprocess

        audio_path = temp_dir / "temp_audio_for_shazam.wav"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract first 30 seconds of audio (enough for identification)
            subprocess.run([
                "ffmpeg", "-i", str(video_path),
                "-vn",  # No video
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "1",
                "-t", "30",  # First 30 seconds
                "-y",
                str(audio_path)
            ], check=True, capture_output=True)

            result = self.identify(audio_path)

            # Cleanup
            if audio_path.exists():
                audio_path.unlink()

            return result

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error extracting audio: {e.stderr.decode()}")
            return None
        except Exception as e:
            logger.error(f"Error extracting audio for identification: {e}")
            return None
