import os
import yt_dlp
from typing import List, Dict, Any, Callable, Optional
from urllib.parse import urlparse
from loguru import logger
from app.config.config import settings

class DownloaderService:
    def __init__(self, download_dir: str = None):
        self.download_dir = download_dir or str(settings.downloads_path)
        os.makedirs(self.download_dir, exist_ok=True)

    @staticmethod
    def normalize_source_url(url: str) -> str:
        """Automatically normalize YouTube channel URLs to point to their /videos tab."""
        url = url.strip()
        
        # If it is a video ID (11 chars) or already a playlist/watch URL, do not modify
        if len(url) == 11 and not ('/' in url or '.' in url):
            return url
            
        if "watch?v=" in url or "youtu.be/" in url or "list=" in url or "playlist" in url:
            return url

        # Check if it looks like a YouTube domain or starts with @
        is_youtube = "youtube.com" in url or "youtu.be" in url or url.startswith("@")
        if not is_youtube:
            return url

        # Normalize protocol if missing
        if not url.startswith("http://") and not url.startswith("https://"):
            if url.startswith("@"):
                url = f"https://www.youtube.com/{url}"
            else:
                url = f"https://{url}"

        try:
            parsed = urlparse(url)
            path = parsed.path.rstrip('/')
            
            # Check if path corresponds to a channel base path
            is_channel = False
            
            # 1. Handle (@username)
            if path.startswith("/@"):
                parts = path.split('/')
                if len(parts) == 2: # No sub-tabs (e.g. /@username)
                    is_channel = True
                    
            # 2. Channel, Custom, User paths
            elif path.startswith("/channel/") or path.startswith("/c/") or path.startswith("/user/"):
                parts = path.split('/')
                if len(parts) == 3: # /channel/UC123 or /c/custom
                    is_channel = True

            if is_channel:
                new_path = f"{path}/videos"
                url = parsed._replace(path=new_path).geturl()
        except Exception as e:
            logger.warning(f"Failed to parse and normalize URL {url}: {e}")

        return url

    def discover_videos(self, source_url: str) -> Dict[str, Any]:
        """Extract metadata from a URL (channel, playlist, or single video) without downloading."""
        source_url = self.normalize_source_url(source_url)
        logger.info(f"Extracting info for URL: {source_url}")
        
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'playlistend': 50 # Limit to 50 videos initially to keep it fast
        }

        videos = []
        playlist_metadata = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_url, download=False)
                
                if not info:
                    return {"playlist": None, "videos": []}
                
                # Check if it is a playlist/channel or a single video
                if 'entries' in info:
                    # Playlist or Channel
                    playlist_title = info.get('title') or "Playlist Sem Título"
                    playlist_desc = info.get('description') or ""
                    
                    # Extract playlist thumbnail
                    playlist_thumb = info.get('thumbnail')
                    if not playlist_thumb and info.get('thumbnails'):
                        playlist_thumb = info['thumbnails'][-1].get('url')
                        
                    for entry in info['entries']:
                        if entry:
                            videos.append(self._format_extracted_info(entry, playlist_title))
                            
                    playlist_metadata = {
                        "title": playlist_title,
                        "description": playlist_desc,
                        "thumbnail_url": playlist_thumb or "",
                        "video_count": len(videos)
                    }
                else:
                    # Single video
                    videos.append(self._format_extracted_info(info))
                    
        except Exception as e:
            logger.error(f"Error extracting metadata from {source_url}: {e}")
            raise ValueError(f"Failed to load URL metadata: {str(e)}")

        return {
            "playlist": playlist_metadata,
            "videos": [v for v in videos if v is not None]
        }

    def download_video(self, video_id: str, progress_callback: Callable[[float], None] = None) -> tuple[str, dict]:
        """Download video to temporary directory using yt-dlp. Returns tuple (local_path, metadata_dict)."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"Downloading video: {video_id}")
        
        output_template = os.path.join(self.download_dir, f"{video_id}.%(ext)s")

        def ytdl_hook(d):
            if d['status'] == 'downloading':
                # Convert bytes downloaded / total to percentage
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    pct = (downloaded / total) * 100
                    if progress_callback:
                        progress_callback(pct)
            elif d['status'] == 'finished':
                if progress_callback:
                    progress_callback(100.0)

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # Prioritize mp4 for compatibility
            'outtmpl': output_template,
            'progress_hooks': [ytdl_hook],
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4'
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # If output format was merged (e.g. mkv to mp4), the path extension might change
                base, ext = os.path.splitext(filename)
                if not os.path.exists(filename):
                    # Check if mp4 exists due to merge
                    if os.path.exists(f"{base}.mp4"):
                        filename = f"{base}.mp4"
                
                logger.info(f"Successfully downloaded video to {filename}")
                return filename, info
        except Exception as e:
            logger.error(f"Failed to download video {video_id}: {e}")
            raise RuntimeError(f"Download failed: {str(e)}")

    def _format_extracted_info(self, entry: Dict[str, Any], playlist_title: str = None) -> Optional[Dict[str, Any]]:
        """Helper to format yt-dlp extracted metadata to our schema."""
        video_id = entry.get('id') or entry.get('url')
        if not video_id:
            return None
            
        # Clean ID in case it's a URL
        if 'youtube.com' in video_id or 'youtu.be' in video_id:
            video_id = video_id.split('v=')[-1].split('&')[0]

        # Extract thumbnails
        thumbnail_url = entry.get('thumbnail')
        if not thumbnail_url and entry.get('thumbnails'):
            thumbnail_url = entry['thumbnails'][-1].get('url')

        duration_sec = entry.get('duration')
        duration_str = ""
        if duration_sec:
            minutes = int(duration_sec // 60)
            seconds = int(duration_sec % 60)
            duration_str = f"{minutes:02d}:{seconds:02d}"

        # Normalize publish date (YYYYMMDD to YYYY-MM-DD)
        raw_date = entry.get('upload_date')
        published_at = ""
        if raw_date and len(raw_date) == 8:
            published_at = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"

        return {
            "id": video_id,
            "title": entry.get('title', 'Unknown Title'),
            "description": entry.get('description', ''),
            "thumbnail_url": thumbnail_url or f"https://img.youtube.com/vi/{video_id}/0.jpg",
            "duration": duration_str,
            "published_at": published_at,
            "view_count": entry.get('view_count', 0),
            "status": "available",
            "playlist_title": playlist_title,
            "tags": entry.get('tags', []),
            "category_id": entry.get('category_id', '22'),
            "default_language": entry.get('language', 'pt')
        }
