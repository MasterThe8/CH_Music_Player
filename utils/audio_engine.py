import threading
import numpy as np
import soundfile as sf
import sounddevice as sd

from PySide6.QtCore import QObject, Signal, QTimer


class AudioEngine(QObject):

    # =====================================================
    # SIGNALS  (same contract as the VLC version)
    # =====================================================

    position_changed = Signal(int)   # milliseconds

    playback_started = Signal()
    playback_paused  = Signal()
    playback_stopped = Signal()

    song_finished = Signal()

    # =====================================================
    # INIT
    # =====================================================

    def __init__(self):
        super().__init__()

        # stem_name -> np.ndarray  (float32, shape: [frames, channels])
        self._stems:       dict[str, np.ndarray] = {}

        # stem_name -> float  (0.0 – 1.0)
        self._stem_volumes: dict[str, float]     = {}

        # Shared sample-rate (all stems must match after resampling)
        self._samplerate: int  = 44100

        self.duration_ms: int  = 0
        self.is_loaded:   bool = False
        self.is_paused:   bool = False

        # Current read head in *frames*
        self._position:   int  = 0

        # Master volume  0.0 – 1.0
        self._master_vol: float = 0.7

        # Guards
        self._is_seeking:  bool = False
        self._is_playing:  bool = False
        self._reached_end: bool = False

        # Thread-safety
        self._lock = threading.Lock()

        # sounddevice stream (opened once, kept alive)
        self._stream: sd.OutputStream | None = None

        # Qt timer for position polling → position_changed signal
        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._emit_position)

    # =====================================================
    # LOAD
    # =====================================================

    def load(self, audio_tracks: dict[str, str]) -> bool:
        """
        audio_tracks: { stem_name: file_path, ... }
        All stems are loaded into RAM as float32 arrays.
        """
        self.stop()
        self._close_stream()

        self._stems.clear()
        self._stem_volumes.clear()
        self.is_loaded = False
        self.duration_ms = 0
        self._position = 0
        self._reached_end = False

        if not audio_tracks:
            return False

        try:
            max_frames  = 0
            samplerate  = None

            for stem_name, path in audio_tracks.items():
                data, sr = sf.read(path, dtype="float32", always_2d=True)

                if samplerate is None:
                    samplerate = sr
                elif sr != samplerate:
                    # Simple drop/repeat resampling (good enough for same-project stems)
                    ratio  = samplerate / sr
                    n_out  = int(len(data) * ratio)
                    xs_old = np.linspace(0, len(data) - 1, len(data))
                    xs_new = np.linspace(0, len(data) - 1, n_out)
                    data   = np.column_stack([
                        np.interp(xs_new, xs_old, data[:, ch])
                        for ch in range(data.shape[1])
                    ]).astype(np.float32)

                self._stems[stem_name]       = data
                self._stem_volumes[stem_name] = 1.0
                max_frames = max(max_frames, len(data))

            if not self._stems:
                return False

            self._samplerate = samplerate or 44100
            self.duration_ms = int(max_frames / self._samplerate * 1000)
            self.is_loaded   = True

            self._open_stream()
            return True

        except Exception as e:
            print(f"[AudioEngine] Load error: {e}")
            return False

    # =====================================================
    # STREAM
    # =====================================================

    def _open_stream(self):
        """Open a sounddevice OutputStream."""
        # All stems mixed to stereo
        self._stream = sd.OutputStream(
            samplerate = self._samplerate,
            channels   = 2,
            dtype      = "float32",
            blocksize  = 1024,
            callback   = self._audio_callback,
            finished_callback = self._stream_finished,
        )

    def _close_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _audio_callback(self, outdata, frames, time_info, status):
        with self._lock:
            if not self._is_playing or not self._stems:
                outdata[:] = 0
                return

            pos   = self._position
            mixed = np.zeros((frames, 2), dtype=np.float32)

            for stem_name, data in self._stems.items():
                vol   = self._stem_volumes.get(stem_name, 1.0) * self._master_vol
                end   = min(pos + frames, len(data))
                chunk = data[pos:end]

                if chunk.shape[1] == 1:
                    chunk = np.repeat(chunk, 2, axis=1)
                elif chunk.shape[1] > 2:
                    chunk = chunk[:, :2]

                n = len(chunk)
                if n > 0:
                    mixed[:n] += chunk * vol

            # Soft clip to prevent distortion when stems stack
            np.clip(mixed, -1.0, 1.0, out=mixed)
            outdata[:] = mixed

            # Advance read head
            max_len = max(len(d) for d in self._stems.values())
            self._position = min(pos + frames, max_len)

            # Signal end-of-file (handled in _emit_position via flag)
            if self._position >= max_len:
                self._is_playing = False
                self._reached_end = True

    def _stream_finished(self):
        pass

    # =====================================================
    # PLAYBACK
    # =====================================================

    def play(self):
        if not self.is_loaded:
            return

        with self._lock:
            self._is_playing = True
            self._reached_end = False

        if self._stream is None:
            self._open_stream()

        if not self._stream.active:
            self._stream.start()

        self.is_paused = False
        self._timer.start()
        self.playback_started.emit()

    def pause(self):
        if not self.is_loaded:
            return

        with self._lock:
            self._is_playing = False

        self.is_paused = True
        self._timer.stop()
        self.playback_paused.emit()

    def resume(self):
        if not self.is_loaded:
            return

        with self._lock:
            self._is_playing = True

        if self._stream and not self._stream.active:
            self._stream.start()

        self.is_paused = False
        self._timer.start()
        self.playback_started.emit()

    def stop(self):
        with self._lock:
            self._is_playing = False
            self._position   = 0
            self._reached_end = False

        if self._stream and self._stream.active:
            self._stream.stop()

        self._timer.stop()
        self.is_paused = False
        self.playback_stopped.emit()

    def toggle_playback(self):
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    # =====================================================
    # SEEK  — frame-accurate, zero drift
    # =====================================================

    def seek(self, seconds: float):
        if not self.is_loaded:
            return

        self._is_seeking  = True
        was_playing = self._is_playing

        # Pause audio thread while we move the read head
        with self._lock:
            self._is_playing = False

        target_frame = int(max(0.0, seconds) * self._samplerate)
        max_frames   = max(len(d) for d in self._stems.values())
        target_frame = min(target_frame, max_frames - 1)

        with self._lock:
            self._position   = target_frame
            self._is_playing = was_playing
            self._reached_end = False

        target_ms = int(target_frame / self._samplerate * 1000)
        self.position_changed.emit(target_ms)

        self._is_seeking = False

        # If stream stopped at end-of-file, restart it
        if was_playing and self._stream and not self._stream.active:
            self._stream.start()

        if not self.is_paused:
            self._timer.start()

    # =====================================================
    # STEM VOLUME
    # =====================================================

    def set_stem_volume(self, stem_name: str, volume: float):
        """volume: 0.0 – 1.0  (or 0 – 100, auto-detected)"""
        if volume > 1.0:
            volume = volume / 100.0
        volume = max(0.0, min(1.0, volume))
        self._stem_volumes[stem_name] = volume

    def mute_stem(self, stem_name: str):
        self.set_stem_volume(stem_name, 0.0)

    def unmute_stem(self, stem_name: str):
        self.set_stem_volume(stem_name, 1.0)

    # =====================================================
    # MASTER VOLUME
    # =====================================================

    def set_master_volume(self, volume: float):
        """volume: 0 – 100"""
        self._master_vol = max(0.0, min(1.0, volume / 100.0))

    # =====================================================
    # GETTERS
    # =====================================================

    def is_playing(self) -> bool:
        return self._is_playing

    def get_position(self) -> int:
        """Current position in milliseconds."""
        return int(self._position / self._samplerate * 1000)

    def get_duration(self) -> int:
        return self.duration_ms

    def get_loaded_stems(self) -> list[str]:
        return list(self._stems.keys())

    # =====================================================
    # INTERNAL
    # =====================================================

    def _emit_position(self):
        pos_ms = self.get_position()
        self.position_changed.emit(pos_ms)

        if self._reached_end:
            self._reached_end = False
            self._timer.stop()
            self.song_finished.emit()
            return

        if not self._is_playing and not self.is_paused:
            self._timer.stop()

    # =====================================================
    # CLEANUP
    # =====================================================

    def cleanup(self):
        self.stop()
        self._close_stream()
        self._stems.clear()