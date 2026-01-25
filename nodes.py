import hashlib
import logging
import os

import folder_paths
import librosa
import numpy as np
import torch

try:
    import pyrubberband as pyrb

    HAS_PYRUBBERBAND = True
except ImportError:
    HAS_PYRUBBERBAND = False

# For IO-based audio save nodes
import comfy.model_management
from comfy_api.latest import IO, UI

logger = logging.getLogger("IramaAudioToolkit")


# -----------------------------
# Irama Text Save
# -----------------------------


class IramaTextSave:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
                "path": (
                    "STRING",
                    {
                        "default": "./ComfyUI/output/[time(%Y-%m-%d)]",
                        "multiline": False,
                    },
                ),
                "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                "filename_delimiter": ("STRING", {"default": "_"}),
                "filename_number_padding": (
                    "INT",
                    {"default": 4, "min": 0, "max": 9, "step": 1},
                ),
            },
            "optional": {
                "base_file_name": ("STRING", {"default": ""}),
                "file_extension": ("STRING", {"default": ".txt"}),
                "encoding": ("STRING", {"default": "utf-8"}),
                "filename_suffix": ("STRING", {"default": ""}),
            },
        }

    OUTPUT_NODE = True
    RETURN_TYPES = ()
    FUNCTION = "save_text_file"
    CATEGORY = "WAS Suite/IO"

    def save_text_file(
        self,
        text,
        path,
        filename_prefix="ComfyUI",
        filename_delimiter="_",
        filename_number_padding=4,
        base_file_name="",
        file_extension=".txt",
        encoding="utf-8",
        filename_suffix="",
    ):
        tokens = TextTokens()
        path = tokens.parseTokens(path)
        filename_prefix = tokens.parseTokens(filename_prefix)

        # If base_file_name is provided, prepend it to filename_prefix
        if base_file_name:
            filename_prefix = base_file_name + filename_delimiter + filename_prefix

        if not os.path.exists(path):
            cstr(f"The path `{path}` doesn't exist! Creating it...").warning.print()
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                cstr(
                    f"The path `{path}` could not be created! Is there write access?\n{e}"
                ).error.print()

        if text.strip() == "":
            cstr(f"There is no text specified to save! Text is empty.").error.print()

        delimiter = filename_delimiter
        number_padding = int(filename_number_padding)
        filename = self.generate_filename(
            path,
            filename_prefix,
            delimiter,
            number_padding,
            file_extension,
            filename_suffix,
        )
        file_path = os.path.join(path, filename)

        if isAllowedFilepath(file_path):
            self.write_text_file(file_path, text, encoding)
            update_history_text_files(file_path)
            return (text, {"ui": {"string": text}})
        else:
            cstr(
                f"'{os.path.abspath(file_path)}' is a write-protected path. Please add it to the whitelist file and restart\n=> {WAS_USER_CONFIG_WHITELIST_DIRS_FILE}"
            ).error.print()
            raise Exception(
                f"'{file_path}' is a write-protected path.\nPlease add it to the whitelist file"
            )

    def generate_filename(
        self, path, prefix, delimiter, number_padding, extension, suffix
    ):
        if number_padding == 0:
            # If number_padding is 0, don't use a numerical suffix
            filename = f"{prefix}{suffix}{extension}"
        else:
            if delimiter:
                pattern = f"{re.escape(prefix)}{re.escape(delimiter)}(\\d{{{number_padding}}}){re.escape(suffix)}{re.escape(extension)}"
            else:
                pattern = f"{re.escape(prefix)}(\\d{{{number_padding}}}){re.escape(suffix)}{re.escape(extension)}"

            existing_counters = [
                int(re.search(pattern, filename).group(1))
                for filename in os.listdir(path)
                if re.match(pattern, filename) and filename.endswith(extension)
            ]
            existing_counters.sort()
            if existing_counters:
                counter = existing_counters[-1] + 1
            else:
                counter = 1
            if delimiter:
                filename = (
                    f"{prefix}{delimiter}{counter:0{number_padding}}{suffix}{extension}"
                )
            else:
                filename = f"{prefix}{counter:0{number_padding}}{suffix}{extension}"

            while os.path.exists(os.path.join(path, filename)):
                counter += 1
                if delimiter:
                    filename = f"{prefix}{delimiter}{counter:0{number_padding}}{suffix}{extension}"
                else:
                    filename = f"{prefix}{counter:0{number_padding}}{suffix}{extension}"

        return filename

    def write_text_file(self, file, content, encoding):
        try:
            with open(file, "w", encoding=encoding, newline="\n") as f:
                f.write(content)
        except OSError:
            cstr(f"Unable to save file `{file}`").error.print()


# -----------------------------
# Irama Audio Batch Stitcher
# -----------------------------


class IramaAudioBatchStitcher:
    """
    Automatically concatenates audio batch from Qwen3-TTS, trimming silence
    from the end of each chunk and inserting configurable silence between chunks.

    Now supports:
    - audio: single AUDIO dict {"waveform": (B,C,T), "sample_rate": sr}
    - audio: list of AUDIO dicts, each with {"waveform": (B,C,T), "sample_rate": sr}
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "silence_threshold": (
                    "FLOAT",
                    {
                        "default": 0.01,
                        "min": 0.0,
                        "max": 0.1,
                        "step": 0.001,
                        "display": "slider",
                    },
                ),
                "gap_duration_ms": (
                    "INT",
                    {
                        "default": 200,
                        "min": 0,
                        "max": 1000,
                        "step": 10,
                        "display": "slider",
                    },
                ),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "stitch_and_trim"
    CATEGORY = "🎧️ Irama Audio Toolkit"

    def stitch_and_trim(self, audio, silence_threshold, gap_duration_ms):
        # Normalize input to a list of AUDIO dicts
        if isinstance(audio, dict) and "waveform" in audio:
            audio_list = [audio]
        elif isinstance(audio, list):
            # Assume list of AUDIO dicts from a batched TTS node
            audio_list = audio
        else:
            raise TypeError(
                f"[IramaAudioBatchStitcher] Unsupported AUDIO type: {type(audio)}"
            )

        # Collect all chunks (each item may have batch dimension >1)
        chunk_waveforms = []
        sample_rate = None

        for idx, a in enumerate(audio_list):
            if not isinstance(a, dict) or "waveform" not in a:
                raise TypeError(
                    f"[IramaAudioBatchStitcher] AUDIO item at index {idx} is not a dict with 'waveform'"
                )

            wf = a["waveform"]  # (B, C, T)
            sr = a.get("sample_rate")
            if sr is None:
                raise ValueError(
                    "[IramaAudioBatchStitcher] Missing 'sample_rate' in AUDIO item"
                )

            if sample_rate is None:
                sample_rate = int(sr)
            elif int(sr) != sample_rate:
                raise ValueError(
                    f"[IramaAudioBatchStitcher] Mismatched sample_rate: got {sr}, expected {sample_rate}"
                )

            if not isinstance(wf, torch.Tensor):
                wf = torch.as_tensor(wf)

            if wf.ndim == 2:
                # (C,T) -> (1,C,T)
                wf = wf.unsqueeze(0)
            elif wf.ndim != 3:
                raise ValueError(
                    f"[IramaAudioBatchStitcher] Expected waveform with shape (B,C,T) or (C,T), got {wf.shape}"
                )

            # Split batch into individual chunks
            for b in range(wf.shape[0]):
                chunk_waveforms.append(wf[b : b + 1])  # (1,C,T)

        if not chunk_waveforms:
            # Nothing to stitch, pass through silence
            return (
                {
                    "waveform": torch.zeros(1, 1, 1, dtype=torch.float32),
                    "sample_rate": sample_rate or 24000,
                },
            )

        # If only one chunk overall, just trim and return
        if len(chunk_waveforms) == 1:
            trimmed = self._trim_silence(
                chunk_waveforms[0], sample_rate, silence_threshold
            )
            return (
                {
                    "waveform": trimmed,
                    "sample_rate": sample_rate,
                },
            )

        gap_samples = int((gap_duration_ms / 1000.0) * sample_rate)
        channels = chunk_waveforms[0].shape[1]

        silence_gap = (
            torch.zeros(
                (1, channels, gap_samples),
                dtype=chunk_waveforms[0].dtype,
                device=chunk_waveforms[0].device,
            )
            if gap_samples > 0
            else None
        )

        # Trim each chunk
        trimmed_chunks = []
        for chunk in chunk_waveforms:
            trimmed_chunk = self._trim_silence(chunk, sample_rate, silence_threshold)
            trimmed_chunks.append(trimmed_chunk)

        # Stitch with gaps
        stitched_parts = []
        for i, chunk in enumerate(trimmed_chunks):
            stitched_parts.append(chunk)
            if i < len(trimmed_chunks) - 1 and silence_gap is not None:
                stitched_parts.append(silence_gap)

        final_audio = torch.cat(stitched_parts, dim=-1)

        return (
            {
                "waveform": final_audio,
                "sample_rate": sample_rate,
            },
        )

    def _trim_silence(self, audio_chunk, sample_rate, threshold):
        waveform = audio_chunk[0]  # (C, T)
        if waveform.shape[-1] == 0:
            return audio_chunk

        frame_size = 1024
        hop_size = 512

        padded = torch.nn.functional.pad(
            waveform,
            (0, frame_size - 1),
            mode="constant",
            value=0,
        )

        n_frames = (padded.shape[-1] - frame_size) // hop_size + 1
        frames = []
        for j in range(n_frames):
            frame = padded[:, j * hop_size : j * hop_size + frame_size]
            frames.append(frame)

        if not frames:
            return audio_chunk

        rms_values = []
        for frame in frames:
            rms = torch.sqrt(torch.mean(frame**2, dim=1).mean())
            rms_values.append(rms.item())

        rms_values = np.array(rms_values)
        above_threshold = np.where(rms_values > threshold)[0]

        if len(above_threshold) == 0:
            return torch.zeros(
                (1, waveform.shape[0], 1),
                dtype=waveform.dtype,
                device=waveform.device,
            )

        last_frame_idx = above_threshold[-1]
        trim_sample = (last_frame_idx + 1) * hop_size + frame_size
        trim_sample = min(trim_sample, waveform.shape[-1])
        trimmed = waveform[:, :trim_sample]
        return trimmed.unsqueeze(0)


# -----------------------------
# Irama Audio Speed Correction
# -----------------------------
class IramaAudioSpeedCorrection:
    """
    Change playback speed of AUDIO using librosa, Rubberband, or resample methods.

    - speed < 1.0 = slower
    - speed > 1.0 = faster

    backends:
      - librosa   : phase-vocoder time-stretch
      - rubberband: high-quality time-stretch (needs pyrubberband + rubberband CLI)
      - resample: resample-in-time (natural slowdown, pitch preserved, minimal artifacts)
    """

    @classmethod
    def INPUT_TYPES(cls):
        backends = ["librosa", "rubberband", "resample"]
        default_backend = "rubberband" if HAS_PYRUBBERBAND else "librosa"

        return {
            "required": {
                "audio": ("AUDIO",),
                "speed": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.5,
                        "max": 2.0,
                        "step": 0.01,
                        "display": "slider",
                        "tooltip": "Speed multiplier (0.5=half speed, 1.0=normal, 2.0=double).",
                    },
                ),
                "backend": (
                    backends,
                    {
                        "default": default_backend,
                        "tooltip": "Method: 'librosa' (fast), 'rubberband' (best quality, needs CLI), 'resample' (natural slowdown via time-resampling).",
                    },
                ),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "apply_speed"
    CATEGORY = "🎧️ Irama Audio Toolkit"

    def apply_speed(self, audio, speed, backend):
        waveform = audio["waveform"]
        sr = int(audio["sample_rate"])

        if speed == 1.0:
            return (audio,)

        speed = float(max(0.5, min(2.0, speed)))
        backend = str(backend).lower()

        if backend == "resample":
            return self._apply_resample(waveform, sr, speed)
        else:
            return self._apply_time_stretch(waveform, sr, speed, backend)

    def _apply_time_stretch(self, waveform, sr, speed, backend):
        b, c, t = waveform.shape
        stretched_list = []

        for bi in range(b):
            chan_stretched = []
            for ci in range(c):
                y = waveform[bi, ci].detach().cpu().numpy().astype(np.float32)
                if y.ndim != 1:
                    y = y.reshape(-1)

                if backend == "rubberband" and HAS_PYRUBBERBAND:
                    try:
                        y_stretch = pyrb.time_stretch(
                            y,
                            sr,
                            speed,
                            rbargs={
                                "--formant": "",
                                "--crisp": "5",
                            },
                        )
                    except Exception as e:
                        print(
                            f"[IramaAudioSpeedCorrection] Rubberband failed ({e}), falling back to librosa."
                        )
                        y_stretch = librosa.effects.time_stretch(y, rate=speed)
                else:
                    if backend == "rubberband" and not HAS_PYRUBBERBAND:
                        print(
                            "[IramaAudioSpeedCorrection] pyrubberband not available; using librosa instead."
                        )
                    y_stretch = librosa.effects.time_stretch(y, rate=speed)

                chan_stretched.append(torch.from_numpy(y_stretch))

            max_len = max(ch.size(0) for ch in chan_stretched)
            chan_padded = []
            for ch in chan_stretched:
                if ch.size(0) < max_len:
                    pad = torch.zeros(max_len - ch.size(0), dtype=ch.dtype)
                    ch = torch.cat([ch, pad], dim=0)
                chan_padded.append(ch.unsqueeze(0))

            chan_tensor = torch.cat(chan_padded, dim=0)
            stretched_list.append(chan_tensor.unsqueeze(0))

        final_waveform = torch.cat(stretched_list, dim=0)

        return (
            {
                "waveform": final_waveform.to(waveform.device),
                "sample_rate": sr,
            },
        )

    def _apply_resample(self, waveform, sr, speed):
        """
        Resample in time: change number of samples so that speed semantics match:

          speed < 1.0 => slower (more samples)
          speed > 1.0 => faster (fewer samples)
        """
        b, c, t = waveform.shape
        speed = float(max(0.5, min(2.0, speed)))

        if speed == 1.0:
            return (
                {
                    "waveform": waveform,
                    "sample_rate": sr,
                },
            )

        new_length = int(t / speed)

        resampled_list = []
        for bi in range(b):
            chan_resampled = []
            for ci in range(c):
                y = waveform[bi, ci].detach().cpu().numpy().astype(np.float32)
                if y.ndim != 1:
                    y = y.reshape(-1)

                try:
                    y_resampled = librosa.resample(
                        y,
                        orig_sr=t,
                        target_sr=new_length,
                    )
                    chan_resampled.append(torch.from_numpy(y_resampled))
                except Exception as e:
                    print(
                        f"[IramaAudioSpeedCorrection] resample (time-resample) failed ({e}), using original."
                    )
                    chan_resampled.append(torch.from_numpy(y))

            max_len = max(ch.size(0) for ch in chan_resampled)
            chan_padded = []
            for ch in chan_resampled:
                if ch.size(0) < max_len:
                    pad = torch.zeros(max_len - ch.size(0), dtype=ch.dtype)
                    ch = torch.cat([ch, pad], dim=0)
                chan_padded.append(ch.unsqueeze(0))

            chan_tensor = torch.cat(chan_padded, dim=0)
            resampled_list.append(chan_tensor.unsqueeze(0))

        final_waveform = torch.cat(resampled_list, dim=0)

        return (
            {
                "waveform": final_waveform.to(waveform.device),
                "sample_rate": sr,
            },
        )


# -----------------------------
# Irama Load Text From File
# -----------------------------
class IramaLoadTextFromFile:
    """
    Load text content from a .txt file in ComfyUI input/output/temp folders.

    Outputs:
      - text: file contents
      - basename: filename without extension (e.g. 'story_01' from 'story_01.txt')
    """

    @classmethod
    def INPUT_TYPES(cls):
        all_files = []
        for dir_name in ["input", "output", "temp"]:
            files = cls.get_files_for_directory(dir_name)
            for f in files:
                if f != "No text files found":
                    all_files.append(f"{dir_name}/{f}")

        if not all_files:
            all_files = ["No text files found in any directory"]

        return {
            "required": {
                "file": (
                    sorted(all_files),
                    {
                        "tooltip": "Select a text file to load (format: directory/filename)",
                    },
                ),
            }
        }

    @classmethod
    def get_files_for_directory(cls, source_dir):
        if source_dir == "input":
            dir_path = folder_paths.get_input_directory()
        elif source_dir == "output":
            dir_path = folder_paths.get_output_directory()
        elif source_dir == "temp":
            dir_path = folder_paths.get_temp_directory()
        else:
            return []

        files = []
        try:
            for f in os.listdir(dir_path):
                if os.path.isfile(os.path.join(dir_path, f)):
                    if f.lower().endswith(".txt"):
                        files.append(f)
        except Exception as e:
            logger.warning(f"Error listing files in {source_dir}: {e}")

        return files

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "base_file_name")
    FUNCTION = "load_text"
    CATEGORY = "🎧️ Irama Audio Toolkit"
    DESCRIPTION = (
        "Load text content from a .txt file and output filename (without extension)"
    )

    def load_text(self, file: str):
        try:
            if not file or file == "No text files found in any directory":
                raise Exception("Please select a valid text file.")

            if "/" not in file:
                raise Exception(f"Invalid file format: {file}")

            source_dir, filename = file.split("/", 1)

            if source_dir == "input":
                dir_path = folder_paths.get_input_directory()
            elif source_dir == "output":
                dir_path = folder_paths.get_output_directory()
            elif source_dir == "temp":
                dir_path = folder_paths.get_temp_directory()
            else:
                raise Exception(f"Invalid source directory: {source_dir}")

            file_path = os.path.join(dir_path, filename)

            if not os.path.exists(file_path):
                raise Exception(f"File not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                text_content = f.read()

            if not text_content.strip():
                raise Exception("File is empty or contains only whitespace")

            base_name = os.path.splitext(os.path.basename(filename))[0]
            return (text_content, base_name)

        except UnicodeDecodeError as e:
            raise Exception(
                f"Encoding error reading file: {str(e)}. File may not be UTF-8 encoded."
            )
        except Exception as e:
            logger.error(f"Failed to load text file: {str(e)}")
            raise Exception(f"Error loading text file: {str(e)}")

    @classmethod
    def IS_CHANGED(cls, file):
        if not file or file == "No text files found in any directory":
            return "no_file"

        if "/" not in file:
            return f"{file}_invalid"

        source_dir, filename = file.split("/", 1)

        if source_dir == "input":
            dir_path = folder_paths.get_input_directory()
        elif source_dir == "output":
            dir_path = folder_paths.get_output_directory()
        elif source_dir == "temp":
            dir_path = folder_paths.get_temp_directory()
        else:
            return f"{file}_invalid_dir"

        file_path = os.path.join(dir_path, filename)

        if not os.path.exists(file_path):
            return f"{file}_not_found"

        try:
            m = hashlib.sha256()
            with open(file_path, "rb") as f:
                m.update(f.read())
            return m.digest().hex()
        except Exception:
            return f"{file}_error"

    @classmethod
    def VALIDATE_INPUTS(cls, file, **kwargs):
        if not file or file == "No text files found in any directory":
            return "No valid text file selected"

        if "/" not in file:
            return f"Invalid file format: {file}"

        source_dir, filename = file.split("/", 1)

        if source_dir == "input":
            dir_path = folder_paths.get_input_directory()
        elif source_dir == "output":
            dir_path = folder_paths.get_output_directory()
        elif source_dir == "temp":
            dir_path = folder_paths.get_temp_directory()
        else:
            return f"Invalid source directory: {source_dir}"

        file_path = os.path.join(dir_path, filename)

        if not os.path.exists(file_path):
            return f"File not found: {filename} in {source_dir}"

        return True


# -----------------------------
# Irama Save Audio Nodes (IO API)
# -----------------------------
class IramaSaveAudio(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="IramaSaveAudio",
            display_name="Irama Save Audio (FLAC)",
            category="🎧️ Irama Audio Toolkit",
            inputs=[
                IO.Audio.Input("audio"),
                IO.String.Input("filename_prefix", default="audio/ComfyUI"),
                IO.String.Input(
                    "base_file_name",
                    default="",
                    tooltip="Optional base filename (e.g. story_01). If set, it is prepended to filename_prefix.",
                ),
            ],
            hidden=[IO.Hidden.prompt, IO.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(
        cls, audio, filename_prefix="audio/ComfyUI", base_file_name="", format="flac"
    ) -> IO.NodeOutput:
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix = filename_prefix + "/"
            filename_prefix = filename_prefix + base_file_name

        return IO.NodeOutput(
            ui=UI.AudioSaveHelper.get_save_audio_ui(
                audio,
                filename_prefix=filename_prefix,
                cls=cls,
                format=format,
            )
        )

    save_flac = execute  # TODO: remove


class IramaSaveAudioMP3(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="IramaSaveAudioMP3",
            display_name="Irama Save Audio (MP3)",
            category="🎧️ Irama Audio Toolkit",
            inputs=[
                IO.Audio.Input("audio"),
                IO.String.Input("filename_prefix", default="audio/ComfyUI"),
                IO.String.Input(
                    "base_file_name",
                    default="",
                    tooltip="Optional base filename (e.g. story_01). If set, it is prepended to filename_prefix.",
                ),
                IO.Combo.Input("quality", options=["V0", "128k", "320k"], default="V0"),
            ],
            hidden=[IO.Hidden.prompt, IO.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(
        cls,
        audio,
        filename_prefix="audio/ComfyUI",
        base_file_name="",
        format="mp3",
        quality="128k",
    ) -> IO.NodeOutput:
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix = filename_prefix + "/"
            filename_prefix = filename_prefix + base_file_name

        return IO.NodeOutput(
            ui=UI.AudioSaveHelper.get_save_audio_ui(
                audio,
                filename_prefix=filename_prefix,
                cls=cls,
                format=format,
                quality=quality,
            )
        )

    save_mp3 = execute  # TODO: remove


class IramaSaveAudioOpus(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="IramaSaveAudioOpus",
            display_name="Irama Save Audio (Opus)",
            category="🎧️ Irama Audio Toolkit",
            inputs=[
                IO.Audio.Input("audio"),
                IO.String.Input("filename_prefix", default="audio/ComfyUI"),
                IO.String.Input(
                    "base_file_name",
                    default="",
                    tooltip="Optional base filename (e.g. story_01). If set, it is prepended to filename_prefix.",
                ),
                IO.Combo.Input(
                    "quality",
                    options=["64k", "96k", "128k", "192k", "320k"],
                    default="128k",
                ),
            ],
            hidden=[IO.Hidden.prompt, IO.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(
        cls,
        audio,
        filename_prefix="audio/ComfyUI",
        base_file_name="",
        format="opus",
        quality="128k",
    ) -> IO.NodeOutput:
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix = filename_prefix + "/"
            filename_prefix = filename_prefix + base_file_name

        return IO.NodeOutput(
            ui=UI.AudioSaveHelper.get_save_audio_ui(
                audio,
                filename_prefix=filename_prefix,
                cls=cls,
                format=format,
                quality=quality,
            )
        )

    save_opus = execute  # TODO: remove


# -----------------------------
# Classic API mappings
# -----------------------------
NODE_CLASS_MAPPINGS = {
    "IramaAudioBatchStitcher": IramaAudioBatchStitcher,
    "IramaAudioSpeedCorrection": IramaAudioSpeedCorrection,
    "IramaLoadTextFromFile": IramaLoadTextFromFile,
    "IramaSaveAudio": IramaSaveAudio,
    "IramaSaveAudioMP3": IramaSaveAudioMP3,
    "IramaSaveAudioOpus": IramaSaveAudioOpus,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IramaAudioBatchStitcher": "🎤 Irama Audio Batch Stitcher (trim silence + gap)",
    "IramaAudioSpeedCorrection": "🎚 Irama Audio Speed Correction",
    "IramaLoadTextFromFile": "📝 Irama Load Text From File",
    "IramaSaveAudio": "💾 Irama Save Audio (FLAC)",
    "IramaSaveAudioMP3": "💾 Irama Save Audio (MP3)",
    "IramaSaveAudioOpus": "💾 Irama Save Audio (Opus)",
}
