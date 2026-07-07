import os
from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from loguru import logger
from app.services.auth_service import AuthService

class YoutubeService:
    def __init__(self, token_data: Dict[str, Any]):
        self.credentials = AuthService.get_user_credentials(token_data)
        self.youtube = build("youtube", "v3", credentials=self.credentials)

    def get_channel_info(self) -> Dict[str, Any]:
        """Fetch active channel details."""
        request = self.youtube.channels().list(part="snippet,statistics", mine=True)
        response = request.execute()
        if not response.get("items"):
            raise ValueError("No channel info found.")
        return response["items"][0]

    def list_playlists(self) -> List[Dict[str, Any]]:
        """List playlists owned by the channel."""
        playlists = []
        request = self.youtube.playlists().list(
            part="snippet,contentDetails", mine=True, maxResults=50
        )
        while request:
            response = request.execute()
            playlists.extend(response.get("items", []))
            request = self.youtube.playlists().list_next(request, response)
        return playlists

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        privacy_status: str = "private",
        tags: Optional[List[str]] = None,
        category_id: str = "22",
        language: str = "pt",
        progress_callback = None
    ) -> str:
        """Upload video to YouTube channel using Resumable Upload."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found at {file_path}")

        body = {
            "snippet": {
                "title": title[:100], # YouTube max length is 100
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
                "defaultLanguage": language
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        # MediaFileUpload for video content chunking
        media = MediaFileUpload(
            file_path, 
            mimetype="video/*", 
            resumable=True, 
            chunksize=1024 * 1024 # 1MB chunks
        )

        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        logger.info(f"Starting YouTube upload for video: {title}")
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = status.progress() * 100
                logger.info(f"Uploading '{title}': {progress:.2f}%")
                if progress_callback:
                    progress_callback(progress)
        
        video_id = response.get("id")
        logger.info(f"Upload complete. Video ID: {video_id}")
        return video_id

    def update_thumbnail(self, video_id: str, thumbnail_path: str):
        """Update thumbnail for a video."""
        if not os.path.exists(thumbnail_path):
            logger.warning(f"Thumbnail path {thumbnail_path} does not exist. Skipping.")
            return

        import mimetypes
        mimetype, _ = mimetypes.guess_type(thumbnail_path)
        if not mimetype or mimetype == "image/*":
            mimetype = "image/jpeg"

        media = MediaFileUpload(thumbnail_path, mimetype=mimetype)
        request = self.youtube.thumbnails().set(
            videoId=video_id,
            media_body=media
        )
        response = request.execute()
        logger.info(f"Thumbnail updated for video ID: {video_id}")
        return response

    def create_playlist(self, title: str, description: str = "", privacy_status: str = "private") -> str:
        """Create a new playlist in the channel. Returns the new playlist ID."""
        body = {
            "snippet": {
                "title": title,
                "description": description,
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
        request = self.youtube.playlists().insert(
            part="snippet,status",
            body=body
        )
        response = request.execute()
        playlist_id = response.get("id")
        logger.info(f"Playlist '{title}' created successfully. ID: {playlist_id}")
        return playlist_id

    def add_video_to_playlist(self, playlist_id: str, video_id: str) -> str:
        """Add a video to a playlist. Returns the playlist item ID."""
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
        request = self.youtube.playlistItems().insert(
            part="snippet",
            body=body
        )
        response = request.execute()
        playlist_item_id = response.get("id")
        logger.info(f"Added video {video_id} to playlist {playlist_id}")
        return playlist_item_id

    def _ensure_aspect_ratio(self, image_path: str, target_aspect: float = 16.0 / 9.0) -> bool:
        """Crop the image to the target aspect ratio if necessary to satisfy YouTube API requirements."""
        try:
            from PIL import Image
            if not os.path.exists(image_path):
                return False
                
            with Image.open(image_path) as img:
                # Convert palette or RGBA to RGB (required for JPEG saving)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    
                width, height = img.size
                current_aspect = float(width) / float(height)
                
                # If aspect ratio is close enough to target, just convert and save if needed
                if abs(current_aspect - target_aspect) < 0.05:
                    if img.mode != "RGB" or img.format != "JPEG":
                        img.save(image_path, "JPEG")
                    return True
                    
                logger.info(f"Resizing image {image_path} from aspect ratio {current_aspect:.2f} to {target_aspect:.2f}")
                if current_aspect > target_aspect:
                    # Image is wider, crop left and right
                    new_width = int(height * target_aspect)
                    left = (width - new_width) // 2
                    right = left + new_width
                    img_cropped = img.crop((left, 0, right, height))
                else:
                    # Image is taller, crop top and bottom
                    new_height = int(width / target_aspect)
                    top = (height - new_height) // 2
                    bottom = top + new_height
                    img_cropped = img.crop((0, top, width, bottom))
                
                img_cropped.save(image_path, "JPEG")
                return True
        except Exception as e:
            logger.warning(f"Failed to process image aspect ratio: {e}")
            return False

    def set_playlist_thumbnail(self, playlist_id: str, thumbnail_path: str):
        """Upload custom thumbnail for a playlist."""
        if not os.path.exists(thumbnail_path):
            logger.warning(f"Playlist thumbnail path {thumbnail_path} does not exist. Skipping.")
            return

        # Ensure aspect ratio is 1:1 (mandated by YouTube API for playlist covers)
        self._ensure_aspect_ratio(thumbnail_path, target_aspect=1.0)

        media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        try:
            request = self.youtube.playlistImages().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "type": "hero"
                    }
                },
                media_body=media
            )
            response = request.execute()
            logger.info(f"Playlist thumbnail uploaded successfully for playlist ID: {playlist_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to upload playlist thumbnail: {e}")
            return None

    def list_channel_videos(self) -> List[Dict[str, Any]]:
        """List videos uploaded by the channel (from its 'uploads' playlist)."""
        # 1. Fetch channel's contentDetails to get the uploads playlist ID
        request = self.youtube.channels().list(part="contentDetails", mine=True)
        response = request.execute()
        if not response.get("items"):
            raise ValueError("No channel info found.")
        
        uploads_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # 2. Fetch videos from the uploads playlist
        videos = []
        request = self.youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50
        )
        
        while request and len(videos) < 50:
            response = request.execute()
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
                
                if video_id:
                    thumb_url = snippet.get("thumbnails", {}).get("high", {}).get("url") or \
                                snippet.get("thumbnails", {}).get("default", {}).get("url")
                                
                    videos.append({
                        "id": video_id,
                        "title": snippet.get("title", "Unknown Title"),
                        "description": snippet.get("description", ""),
                        "thumbnail_url": thumb_url or f"https://img.youtube.com/vi/{video_id}/0.jpg",
                        "duration": "",
                        "published_at": snippet.get("publishedAt", "")[:10] if snippet.get("publishedAt") else "",
                        "view_count": 0,
                        "status": "available",
                        "playlist_title": "Uploads",
                        "tags": [],
                        "category_id": "22",
                        "default_language": "pt"
                    })
            request = self.youtube.playlistItems().list_next(request, response)
            
        return videos
