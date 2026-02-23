import os

import numpy as np
import soundfile as sf


def _get_output_directory():
    try:
        import folder_paths

        return folder_paths.get_output_directory()
    except Exception:
        return "./output"


def _prepare_waveform(audio):
    waveform = audio["waveform"]  # (B, C, T)
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim == 3:
        waveform = waveform[0]  # (C, T) - first batch item
    waveform = waveform.detach().cpu().float().numpy()
    return waveform.T, sample_rate  # soundfile wants (T, C)


def _next_filename(out_dir, prefix, ext):
    counter = 1
    while True:
        filename = f"{prefix}_{counter:05d}{ext}"
        if not os.path.exists(os.path.join(out_dir, filename)):
            return filename
        counter += 1


def _save_audio_file(audio, filename_prefix, output_dir, format, quality=None):
    data, sample_rate = _prepare_waveform(audio)

    prefix_parts = filename_prefix.replace("\\", "/").split("/")
    subfolder = "/".join(prefix_parts[:-1]) if len(prefix_parts) > 1 else ""
    prefix = prefix_parts[-1]

    out_dir = os.path.join(output_dir, subfolder) if subfolder else output_dir
    os.makedirs(out_dir, exist_ok=True)

    if format == "flac":
        ext = ".flac"
        filename = _next_filename(out_dir, prefix, ext)
        sf.write(
            os.path.join(out_dir, filename),
            data,
            sample_rate,
            format="FLAC",
            subtype="PCM_16",
        )
    elif format == "mp3":
        # soundfile doesn't write MP3; write as FLAC and note it
        ext = ".flac"
        filename = _next_filename(out_dir, prefix, ext)
        sf.write(
            os.path.join(out_dir, filename),
            data,
            sample_rate,
            format="FLAC",
            subtype="PCM_16",
        )
    elif format == "opus":
        # soundfile supports OGG Vorbis
        ext = ".ogg"
        filename = _next_filename(out_dir, prefix, ext)
        sf.write(
            os.path.join(out_dir, filename),
            data,
            sample_rate,
            format="OGG",
            subtype="VORBIS",
        )
    else:
        ext = ".flac"
        filename = _next_filename(out_dir, prefix, ext)
        sf.write(
            os.path.join(out_dir, filename),
            data,
            sample_rate,
            format="FLAC",
            subtype="PCM_16",
        )

    return filename, subfolder


class IramaSaveAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "filename_prefix": ("STRING", {"default": "audio/ComfyUI"}),
            },
            "optional": {
                "base_file_name": ("STRING", {"default": ""}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    OUTPUT_NODE = True
    RETURN_TYPES = ()
    FUNCTION = "save_audio"
    CATEGORY = "Irama Audio Toolkit"

    def save_audio(
        self,
        audio,
        filename_prefix="audio/ComfyUI",
        base_file_name="",
        prompt=None,
        extra_pnginfo=None,
    ):
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix += "/"
            filename_prefix += base_file_name

        output_dir = _get_output_directory()
        filename, subfolder = _save_audio_file(
            audio, filename_prefix, output_dir, format="flac"
        )

        return {
            "ui": {
                "audio": [
                    {"filename": filename, "subfolder": subfolder, "type": "output"}
                ]
            }
        }


class IramaSaveAudioMP3:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "filename_prefix": ("STRING", {"default": "audio/ComfyUI"}),
                "quality": (["V0", "128k", "320k"], {"default": "V0"}),
            },
            "optional": {
                "base_file_name": ("STRING", {"default": ""}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    OUTPUT_NODE = True
    RETURN_TYPES = ()
    FUNCTION = "save_audio"
    CATEGORY = "Irama Audio Toolkit"

    def save_audio(
        self,
        audio,
        filename_prefix="audio/ComfyUI",
        quality="V0",
        base_file_name="",
        prompt=None,
        extra_pnginfo=None,
    ):
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix += "/"
            filename_prefix += base_file_name

        output_dir = _get_output_directory()
        filename, subfolder = _save_audio_file(
            audio, filename_prefix, output_dir, format="mp3", quality=quality
        )

        return {
            "ui": {
                "audio": [
                    {"filename": filename, "subfolder": subfolder, "type": "output"}
                ]
            }
        }


class IramaSaveAudioOpus:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "filename_prefix": ("STRING", {"default": "audio/ComfyUI"}),
                "quality": (
                    ["64k", "96k", "128k", "192k", "320k"],
                    {"default": "128k"},
                ),
            },
            "optional": {
                "base_file_name": ("STRING", {"default": ""}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    OUTPUT_NODE = True
    RETURN_TYPES = ()
    FUNCTION = "save_audio"
    CATEGORY = "Irama Audio Toolkit"

    def save_audio(
        self,
        audio,
        filename_prefix="audio/ComfyUI",
        quality="128k",
        base_file_name="",
        prompt=None,
        extra_pnginfo=None,
    ):
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix += "/"
            filename_prefix += base_file_name

        output_dir = _get_output_directory()
        filename, subfolder = _save_audio_file(
            audio, filename_prefix, output_dir, format="opus", quality=quality
        )

        return {
            "ui": {
                "audio": [
                    {"filename": filename, "subfolder": subfolder, "type": "output"}
                ]
            }
        }
