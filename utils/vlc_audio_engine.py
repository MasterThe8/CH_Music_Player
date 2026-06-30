"""
VLC Audio Engine — Fast Mode
Plays multitrack stems via VLC media players.
Seek is supported via barrier-sync method.
"""

import vlc

from PySide6.QtCore import QObject, Signal, QTimer


class VLCEngine(QObject):

    # =====================================================
    # SIGNALS
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

        self._vlc_instance: vlc.Instance | None = None
        self._players: dict[str, vlc.MediaPlayer] = {}
        self._stem_volumes: dict[str, float] = {}

        self.duration_ms: int  = 0
        self.is_loaded:   bool = False
        self.is_paused:   bool = False

        self._master_vol:  float = 0.7
        self._is_playing:  bool  = False
        self._reached_end: bool  = False
        self._end_fired:   bool  = False

        # Pending seek target (ms), applied on next _sync_and_play
        self._pending_seek_ms: int | None = None

        # Timer untuk polling posisi
        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._emit_position)

        # Timer untuk barrier sync (tunggu VLC buffer sebelum sinkronisasi)
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(self._sync_and_play)

        self._vlc_instance = vlc.Instance("--quiet", "--no-video")

    # =====================================================
    # LOAD
    # =====================================================

    def load(self, audio_tracks: dict[str, str]) -> bool:
        self.stop()
        self._release_players()

        self._stem_volumes.clear()
        self.is_loaded    = False
        self.duration_ms  = 0
        self._end_fired   = False
        self._pending_seek_ms = None

        if not audio_tracks:
            return False

        try:
            max_dur = 0

            for stem_name, path in audio_tracks.items():
                media = self._vlc_instance.media_new(path)
                media.parse_with_options(vlc.MediaParseFlag.local, 5000)

                player = self._vlc_instance.media_player_new()
                player.set_media(media)

                self._stem_volumes[stem_name] = 1.0
                vol_int = int(1.0 * self._master_vol * 100)
                player.audio_set_volume(max(0, min(200, vol_int)))

                events = player.event_manager()
                events.event_attach(
                    vlc.EventType.MediaPlayerEndReached,
                    self._on_end_reached
                )

                self._players[stem_name] = player

                dur = media.get_duration()
                if dur > 0:
                    max_dur = max(max_dur, dur)

            if not self._players:
                return False

            self.duration_ms = max_dur
            self.is_loaded   = True
            return True

        except Exception as e:
            print(f"[VLCEngine] Load error: {e}")
            return False

    # =====================================================
    # PLAYBACK
    # =====================================================

    def play(self):
        """
        Memulai semua player dengan sinkronisasi:
        1. Play semua → VLC mulai buffer
        2. Tunggu 150ms (barrier) → pause semua + set_time ke posisi yang sama
        3. Resume semua dalam satu tick loop → sinkron
        """
        if not self.is_loaded:
            return

        self._end_fired   = False
        self._reached_end = False

        # Mute sementara untuk mencegah audio terdengar sebelum sync selesai
        self._mute_all_players()

        # Step 1: kick semua player agar VLC mulai decode/buffer
        for player in self._players.values():
            player.play()

        self._is_playing = False  # belum benar-benar "playing" sampai sync selesai
        self.is_paused   = False

        # Step 2: tunggu VLC buffer, lalu sync
        # 150ms cukup untuk single-file; naikkan ke 250ms jika file besar/lambat
        self._sync_timer.start(150)

    def _sync_and_play(self):
        """
        Barrier sync: pause semua player, paksa ke posisi yang sama,
        lalu resume serentak dalam satu Qt event loop tick.
        """
        seek_target = self._pending_seek_ms if self._pending_seek_ms is not None else 0
        self._pending_seek_ms = None

        if len(self._players) == 1:
            # Bypass barrier sync for single track (prevent async set_time overshoot)
            player = next(iter(self._players.values()))
            if seek_target > 0:
                player.set_time(seek_target)
            self._restore_all_volumes()
        else:
            # Pause semua dulu
            for player in self._players.values():
                player.set_pause(1)

            # Set semua ke posisi yang sama — loop ketat tanpa yield
            for player in self._players.values():
                player.set_time(seek_target)

            # Restore volume sebelum resume
            self._restore_all_volumes()

            # Resume semua dalam satu tight loop (paling sinkron yang bisa dicapai)
            for player in self._players.values():
                player.set_pause(0)

        self._is_playing = True
        self.is_paused   = False
        self._timer.start()
        self.playback_started.emit()

        # Update durasi setelah player aktif
        QTimer.singleShot(200, self._update_duration)

    def _update_duration(self):
        max_dur = 0
        for player in self._players.values():
            dur = player.get_length()
            if dur > 0:
                max_dur = max(max_dur, dur)
        if max_dur > 0:
            self.duration_ms = max_dur

    def pause(self):
        if not self.is_loaded:
            return

        # Batalkan sync yang sedang menunggu
        self._sync_timer.stop()

        for player in self._players.values():
            player.set_pause(1)

        self._is_playing = False
        self.is_paused   = True
        self._timer.stop()
        self.playback_paused.emit()

    def resume(self):
        """
        Resume dari paused state — re-sync posisi sebelum lanjut
        untuk menghindari drift yang terakumulasi.
        """
        if not self.is_loaded:
            return

        # Ambil posisi dari player pertama sebagai referensi
        ref_pos = self._get_reference_position()
        self._pending_seek_ms = ref_pos

        self._mute_all_players()

        # Kick semua player
        for player in self._players.values():
            player.set_pause(0)

        # Sync kembali dengan delay singkat
        self._sync_timer.start(80)

    def stop(self):
        self._sync_timer.stop()

        for player in self._players.values():
            player.stop()

        self._is_playing  = False
        self.is_paused    = False
        self._reached_end = False
        self._end_fired   = False
        self._pending_seek_ms = None
        self._timer.stop()
        self.playback_stopped.emit()

    def toggle_playback(self):
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    # =====================================================
    # SEEK  — didukung via barrier sync
    # =====================================================

    def seek(self, seconds: float):
        """
        Seek ke posisi (detik). Semua player di-sync ke posisi yang sama.
        Aman dipanggil saat playing maupun paused.
        """
        if not self.is_loaded:
            return

        target_ms = int(seconds * 1000)
        if self.duration_ms > 0:
            target_ms = max(0, min(target_ms, self.duration_ms))
        else:
            target_ms = max(0, target_ms)

        if self._is_playing:
            # Pause → set posisi → resume sync
            self._sync_timer.stop()
            self._pending_seek_ms = target_ms

            self._mute_all_players()

            for player in self._players.values():
                player.set_pause(1)

            # Langsung trigger sync (tanpa delay tambahan karena sudah buffer)
            self._sync_timer.start(80)

        else:
            # Sedang paused atau sedang menunggu sync (baru saja di-play)
            if self._sync_timer.isActive():
                self._pending_seek_ms = target_ms
            else:
                for player in self._players.values():
                    player.set_time(target_ms)

    # =====================================================
    # STEM VOLUME
    # =====================================================

    def set_stem_volume(self, stem_name: str, volume: float):
        if volume > 1.0:
            volume = volume / 100.0
        volume = max(0.0, min(1.0, volume))
        self._stem_volumes[stem_name] = volume

        player = self._players.get(stem_name)
        if player:
            vol_int = int(volume * self._master_vol * 100)
            player.audio_set_volume(max(0, min(200, vol_int)))

    def mute_stem(self, stem_name: str):
        self.set_stem_volume(stem_name, 0.0)

    def unmute_stem(self, stem_name: str):
        self.set_stem_volume(stem_name, 1.0)

    # =====================================================
    # MASTER VOLUME
    # =====================================================

    def set_master_volume(self, volume: float):
        self._master_vol = max(0.0, min(1.0, volume / 100.0))
        for stem_name, player in self._players.items():
            stem_vol = self._stem_volumes.get(stem_name, 1.0)
            vol_int  = int(stem_vol * self._master_vol * 100)
            player.audio_set_volume(max(0, min(200, vol_int)))

    # =====================================================
    # GETTERS
    # =====================================================

    def is_playing(self) -> bool:
        return self._is_playing

    def get_position(self) -> int:
        return self._get_reference_position()

    def get_duration(self) -> int:
        return self.duration_ms

    def get_loaded_stems(self) -> list[str]:
        return list(self._players.keys())

    # =====================================================
    # INTERNAL HELPERS
    # =====================================================

    def _get_reference_position(self) -> int:
        """
        Ambil posisi dari semua player, kembalikan nilai median
        untuk meminimalkan dampak outlier (player yang sedikit drift).
        """
        if not self._players:
            return 0

        times = []
        for player in self._players.values():
            t = player.get_time()
            if t is not None and t >= 0:
                times.append(t)

        if not times:
            return 0

        times.sort()
        mid = len(times) // 2
        return times[mid]

    def _mute_all_players(self):
        """Senyapkan semua player sementara (volume = 0) tanpa mengubah stem_volumes."""
        for player in self._players.values():
            player.audio_set_volume(0)

    def _restore_all_volumes(self):
        """Kembalikan volume semua player sesuai stem_volumes + master_vol."""
        for stem_name, player in self._players.items():
            stem_vol = self._stem_volumes.get(stem_name, 1.0)
            vol_int  = int(stem_vol * self._master_vol * 100)
            player.audio_set_volume(max(0, min(200, vol_int)))

    def _emit_position(self):
        pos_ms = self._get_reference_position()
        self.position_changed.emit(pos_ms)

        if self._reached_end and not self._end_fired:
            self._end_fired  = True
            self._is_playing = False
            self._timer.stop()
            self.song_finished.emit()

    def _on_end_reached(self, event):
        self._reached_end = True

    def _release_players(self):
        for player in self._players.values():
            try:
                player.stop()
                player.release()
            except Exception:
                pass
        self._players.clear()

    # =====================================================
    # CLEANUP
    # =====================================================

    def cleanup(self):
        self.stop()
        self._release_players()
        if self._vlc_instance:
            try:
                self._vlc_instance.release()
            except Exception:
                pass
            self._vlc_instance = None