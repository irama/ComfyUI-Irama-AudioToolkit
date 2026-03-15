import json


class IramaWhisperToSRTText:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "alignment": ("whisper_alignment",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("srt_text",)
    FUNCTION = "to_srt"
    CATEGORY = "Irama"

    def seconds_to_srt_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def to_srt(self, alignment):
        if isinstance(alignment, str):
            data = json.loads(alignment)
        else:
            data = alignment

        srt_lines = []
        for i, entry in enumerate(data, start=1):
            start_time = self.seconds_to_srt_time(entry['start'])
            end_time = self.seconds_to_srt_time(entry['end'])
            text = entry['value']

            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(text)
            srt_lines.append("")

        return ('\n'.join(srt_lines),)
