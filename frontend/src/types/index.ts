export interface Account {
  id: number;
  account_name: string;
  channel_id: string;
  channel_title: string;
  created_at: string;
}

export interface DownloadJob {
  id: string;
  video_id: string;
  title: string;
  format: 'mp3' | 'mp4';
  resolution: number;
  status: 'queued' | 'running' | 'completed' | 'error' | 'expired' | 'cancelled';
  progress: number;
  message: string;
  file_size: number;
  expires_at: string;
  file_url: string | null;
}

export interface DownloadStatus {
  available: boolean;
  mode: 'local' | 'remote' | 'companion';
  retention_hours: number;
  engine: {
    version: string;
    updating: boolean;
    last_check: string | null;
    update_error: string;
    auto_update: boolean;
    update_hours: number;
    channel: string;
    ffmpeg: boolean;
    javascript: boolean;
  } | null;
}

export interface EmptyVideo {
  id: string;
  title: string;
  published_at: string;
  thumbnail_url: string;
}

export interface DescriptionProposal {
  structure?: { ensemble: string; history: string; social_text: string; main_follow: string; playlists: string; body: string; source: {id: string; title: string} | null };
  video_id: string;
  title: string;
  published_at: string;
  identity: { work: string; composer: string; arranger: string };
  description: string;
  match_type: 'same_work' | 'composer' | 'arranger' | 'none';
  source: { id: string; title: string } | null;
  links_source: { id: string; title: string } | null;
  reason: string;
}

export interface ApplyResult {
  video_id: string;
  status: 'updated' | 'skipped' | 'error';
  message: string;
}

export interface VideoInfo {
  id: string;
  title: string;
  description: string;
  thumbnail_url: string;
  duration: string;
  published_at: string;
  view_count: number;
  status: string;
  playlist_title?: string;
  tags?: string[];
  category_id?: string;
  default_language?: string;
}

export interface PlaylistInfo {
  title: string;
  description?: string;
  thumbnail_url?: string;
  video_count: number;
}

export interface DiscoveryResponse {
  playlist?: PlaylistInfo | null;
  videos: VideoInfo[];
}

export interface Task {
  id: number;
  video_id: string;
  title: string;
  description?: string;
  tags?: string;
  category_id?: string;
  language?: string;
  thumbnail_url?: string;
  
  source_channel_id: string;
  source_channel_title: string;
  target_channel_id: string;
  target_channel_title?: string;
  
  status: 'pending' | 'downloading' | 'uploading' | 'completed' | 'error';
  progress: number;
  error_message?: string;
  privacy_status: 'public' | 'unlisted' | 'private';
  scheduled_at?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface AppSettings {
  default_account_id: string;
  default_channel_id: string;
  temp_downloads_dir: string;
  theme: 'light' | 'dark';
}
