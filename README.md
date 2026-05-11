# ◈ Lumina Music Player

A modern, elegant music player built with **PySide6** — Dark Blue theme.

---

## ✦ Features

| Feature | Description |
|---|---|
| **Left Panel** | Playlist sidebar — show/hide with `Ctrl+[` or the `‹` toggle |
| **Main Panel** | Song library + switchable Lyrics viewer |
| **Right Panel** | Now Playing info, cover art, queue — show/hide with `Ctrl+]` |
| **Bottom Bar** | Fixed player bar: progress, transport, volume, repeat, shuffle |
| **Database** | JSON persistence in `~/.lumina/db.json` |
| **Scanner** | Background folder scanner, extracts metadata via `mutagen` |
| **Playlists** | Create, rename, delete; add/remove songs |

---

## ✦ Project Structure

```
music_player/
├── main.py                    # Entry point
├── requirements.txt
├── assets/
│   └── style.qss              # Dark blue QSS theme
├── components/
│   ├── main_window.py         # Root window, wires all signals
│   ├── playlist_panel.py      # Left sidebar (playlists + nav)
│   ├── main_panel.py          # Center: song table ↔ lyrics
│   ├── now_playing_panel.py   # Right sidebar (Now Playing + queue)
│   └── player_bar.py          # Fixed bottom player bar
└── utils/
    ├── database.py            # JSON DB manager + data models
    ├── audio_engine.py        # QMediaPlayer wrapper
    └── scanner.py             # Folder scanner + metadata extraction
```

---

## ✦ Installation

```bash
# 1. Clone / extract the project
cd music_player

# 2. Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

---

## ✦ Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Play / Pause |
| `→` Right | Next song |
| `←` Left | Previous song |
| `Ctrl+L` | Toggle Lyrics view |
| `Ctrl+[` | Toggle left (playlist) panel |
| `Ctrl+]` | Toggle right (now playing) panel |

---

## ✦ Adding Music

1. Click **⊕ Add Folder** in the main panel top bar, or
2. Navigate to **Folders** in the left sidebar.
3. Select your music directory — Lumina will scan it in the background.
4. Supported formats: **MP3, FLAC, WAV, OGG, M4A, AAC, WMA, OPUS**

---

## ✦ Data Model (JSON)

The database lives at `~/.lumina/db.json`:

```json
{
  "version": "1.0",
  "songs": {
    "<song_id>": {
      "id": "abc123",
      "title": "Song Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "duration": 214.5,
      "file_path": "/music/song.mp3",
      "cover_art": "<base64>",
      "lyrics": "Verse 1 ...",
      "genre": "Electronic",
      "year": "2023",
      "track_number": 1,
      "play_count": 7,
      "last_played": "2024-01-15T18:30:00",
      "date_added": "2024-01-01T10:00:00"
    }
  },
  "playlists": {
    "<playlist_id>": {
      "id": "pl_xyz",
      "name": "My Playlist",
      "description": "",
      "song_ids": ["abc123", "def456"],
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-02T12:00:00"
    }
  },
  "settings": {
    "volume": 0.7,
    "shuffle": false,
    "repeat_mode": "none",
    "show_playlist_panel": true,
    "show_now_playing_panel": true,
    "music_folders": ["/home/user/Music"]
  },
  "queue": [],
  "history": []
}
```

---

## ✦ Architecture Notes

- **AudioEngine** wraps `QMediaPlayer` and owns all playback state.
- All inter-component communication uses **Qt signals/signals** — no direct coupling.
- **FolderScanner** runs in a `QThread`; the UI is never blocked during scanning.
- **DatabaseManager** serializes/deserializes to JSON with Python dataclasses.
- The stylesheet (`style.qss`) uses Qt Object Names for clean CSS-like targeting.

---

## ✦ Extending

### Add new panel view
Add a page to `main_panel.py`'s `QStackedWidget` and emit a signal to switch to it.

### Add equalizer
Implement a `QAudioFilter` subclass and wire it into `AudioEngine._audio_output`.

### Add streaming / online search
Extend `DatabaseManager` with an online metadata provider and add an async fetch in `ScanWorker`.

---

*Built with PySide6 · MIT License*
