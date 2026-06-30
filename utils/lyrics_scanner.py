import re


class LyricsScanner:

    @staticmethod
    def _is_invalid_line(text: str) -> bool:
        """
        Filter useless lyric lines like:
        -
        _
        <i></i>
        """

        cleaned = text.strip()

        # remove empty italic tags
        cleaned = re.sub(
            r"</?i>",
            "",
            cleaned,
            flags=re.IGNORECASE
        ).strip()

        # line becomes empty
        if not cleaned:
            return True

        # only symbols like -, _, ---, ___
        if re.fullmatch(r"[-_]+", cleaned):
            return True

        return False

    @staticmethod
    def extract_lyrics(chart_path):

        try:

            with open(
                chart_path,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as f:

                content = f.read()

            events_match = re.search(
                r"\[Events\]\s*\{(.*?)\}",
                content,
                re.DOTALL
            )

            if not events_match:
                return ""

            events_content = events_match.group(1)

            lines = events_content.splitlines()

            lyrics = []
            current_line = ""

            for line in lines:

                line = line.strip()

                # ---------------------------------
                # phrase separator
                # ---------------------------------
                if 'E "phrase_start"' in line:

                    final_line = current_line.strip()

                    if (
                        final_line and
                        not LyricsScanner._is_invalid_line(final_line)
                    ):
                        lyrics.append(final_line)

                    current_line = ""

                # ---------------------------------
                # lyric extraction
                # ---------------------------------
                lyric_match = re.search(
                    r'E "lyric (.*?)"',
                    line
                )

                if lyric_match:

                    lyric = lyric_match.group(1)

                    # filter Rock Band vocal join symbol
                    lyric = lyric.replace("=", "-")

                    # remove weird symbols
                    lyric = lyric.replace("+", "")
                    lyric = lyric.replace("#", "")
                    lyric = lyric.replace("$", "")
                    lyric = lyric.replace("-$", "")

                    # ---------------------------------
                    # syllable join
                    # ---------------------------------
                    if lyric.endswith("-"):

                        current_line += lyric[:-1]

                    else:

                        current_line += lyric + " "

            # ---------------------------------
            # append last line
            # ---------------------------------
            final_line = current_line.strip()

            if (
                final_line and
                not LyricsScanner._is_invalid_line(final_line)
            ):
                lyrics.append(final_line)

            return "\n\n".join(lyrics)

        except Exception as e:

            print(f"Lyrics scanner error: {e}")

            return ""