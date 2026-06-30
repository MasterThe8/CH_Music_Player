from mido import MidiFile


class MidiLyricsScanner:
    PHRASE_NOTE = 105

    @staticmethod
    def clean_lyric(text):
        """
        Bersihkan marker gameplay vocal Rock Band
        """

        text = text.replace("-$", "")
        text = text.replace("+", "")
        text = text.replace("#", "")
        text = text.replace("$", "")

        # RB/GH syllable continuation
        text = text.replace("=", "-")

        return text.strip()

    @staticmethod
    def extract_lyrics(mid_path):
        try:
            mid = MidiFile(mid_path)

            lyrics = []
            current_line = ""

            for track in mid.tracks:

                # =====================================
                # TRACK FILTER
                # =====================================

                track_name = ""

                for msg in track:
                    if msg.is_meta and msg.type == "track_name":
                        track_name = msg.name.upper()
                        break

                # hanya vocal utama
                if "VOCALS" not in track_name:
                    continue

                # skip harmony
                if "HARM" in track_name:
                    continue

                absolute_tick = 0

                for msg in track:
                    absolute_tick += msg.time

                    # =====================================
                    # PHRASE MARKER
                    # =====================================

                    if not msg.is_meta:

                        # phrase start
                        if (
                            msg.type == "note_on"
                            and msg.note == MidiLyricsScanner.PHRASE_NOTE
                            and msg.velocity > 0
                        ):

                            # append bait sebelumnya
                            if current_line.strip():
                                lyrics.append(current_line.strip())
                                current_line = ""

                        continue

                    # =====================================
                    # LYRIC EVENTS
                    # =====================================

                    if msg.type == "lyrics":

                        lyric = msg.text.strip()

                        lyric = MidiLyricsScanner.clean_lyric(lyric)

                        # skip kosong
                        if not lyric:
                            continue

                        # skip marker text aneh
                        if lyric.lower() in [
                            "phrase_start",
                            "phrase_end"
                        ]:
                            continue

                        # sambung syllable
                        if lyric.endswith("-"):
                            current_line += lyric[:-1]
                        else:
                            current_line += lyric + " "

            # append terakhir
            if current_line.strip():
                lyrics.append(current_line.strip())

            return "\n\n".join(lyrics)

        except Exception as e:
            print(f"MIDI lyrics scanner error: {e}")
            return ""


# TEST
# if __name__ == "__main__":
#     result = MidiLyricsScanner.extract_lyrics("notes.mid")
#     print(result)