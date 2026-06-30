# CH MP (Clone Hero Music Player)

CH MP (Clone Hero Music Player) is a desktop music player built with **Python** and **PySide6**, designed specifically for managing and playing Clone Hero song libraries. It provides fast library scanning, playlist management, synchronized lyrics support, and an intuitive user interface.

## Features

* 🎵 Play audio files using VLC backend
* 📂 Scan and index Clone Hero song folders
* 🗂 Organize songs in a local database
* 🔍 Fast search and filtering
* 📃 Playlist management
* 🎤 Display synchronized lyrics (MIDI/Lyrics support)
* 🎹 Parse Clone Hero `.mid` files for lyric extraction
* 🎨 Modern Qt stylesheet interface
* 💾 Automatically save library information

## Project Structure

```text
CH MP/
├── assets/          # Icons and UI styles
├── components/      # User interface components
├── core/            # Core application modules
├── utils/           # Audio engine, scanner, parser, helper modules
├── main.py          # Application entry point
├── requirements.txt
└── README.md
```

## Requirements

* Python 3.11 or newer
* VLC Media Player installed on the system

Python packages:

```bash
pip install -r requirements.txt
```

## Dependencies

Main libraries used by this project:

* PySide6
* mutagen
* python-vlc

Additional dependencies may be required depending on future features.

## Running the Application

```bash
python main.py
```

## Supported Files

Audio:

* MP3
* OGG
* FLAC
* WAV
* Other formats supported by VLC

Lyrics:

* MIDI (.mid)

Clone Hero:

* Clone Hero song folders
* notes.mid
* song.ini (when available)

## Screenshots

Screenshots can be added here.

```
docs/screenshot-main.png
docs/screenshot-player.png
```

## License

This project is intended for personal and educational purposes unless stated otherwise.
