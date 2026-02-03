import numpy as np
import torch


class IramaAudioBatchStitcher:
    """
    Automatically concatenates audio batch from Qwen3-TTS, trimming silence
    from the end of each chunk and inserting configurable silence between chunks.

    Now supports:
    - audio: single AUDIO dict {waveform: (B,C,T), sample_rate: sr}
    - audio: list of AUDIO dicts, each with {waveform: (B,C,T), sample_rate: sr}
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
    CATEGORY = "Irama Audio Toolkit"

    def stitch_and_trim(self, audio, silence_threshold, gap_duration_ms):
        # Normalize input to a list of AUDIO dicts
        if isinstance(audio, dict) and "waveform" in audio:
            audio_list = [audio]
        elif isinstance(audio, list):
            audio_list = audio
        else:
            raise TypeError(
                f"IramaAudioBatchStitcher: Unsupported AUDIO type {type(audio)}"
            )

        # Assume list of AUDIO dicts from a batched TTS node
        chunk_waveforms = []
        sample_rate = None

        for idx, a in enumerate(audio_list):
            if not isinstance(a, dict) or "waveform" not in a:
                raise TypeError(
                    f"IramaAudioBatchStitcher: AUDIO item at index {idx} is not a dict with 'waveform'"
                )

            wf = a["waveform"]  # (B, C, T)
            sr = a.get("sample_rate")
            if sr is None:
                raise ValueError(
                    "IramaAudioBatchStitcher: Missing 'sample_rate' in AUDIO item"
                )

            if sample_rate is None:
                sample_rate = int(sr)
            elif int(sr) != sample_rate:
                raise ValueError(
                    f"IramaAudioBatchStitcher: Mismatched sample_rate (got {sr}, expected {sample_rate})"
                )

            if not isinstance(wf, torch.Tensor):
                wf = torch.as_tensor(wf)

            if wf.ndim == 2:
                # (C,T) -> (1,C,T)
                wf = wf.unsqueeze(0)
            elif wf.ndim != 3:
                raise ValueError(
                    f"IramaAudioBatchStitcher: Expected waveform with shape (B,C,T) or (C,T), "
                    f"got {wf.shape}"
                )

            # Split batch into individual chunks
            for b in range(wf.shape[0]):
                chunk_waveforms.append(wf[b : b + 1])  # (1,C,T)

        if not chunk_waveforms:
            # Nothing to stitch, pass through silence
            return (
                {
                    "waveform": torch.zeros((1, 1, 1), dtype=torch.float32),
                    "sample_rate": sample_rate or 24000,
                },
            )

        # If only one chunk overall, just trim and return
        if len(chunk_waveforms) == 1:
            trimmed = self._trim_silence(
                chunk_waveforms[0], sample_rate, silence_threshold
            )
            return ({"waveform": trimmed, "sample_rate": sample_rate},)

        gap_samples = (
            int(gap_duration_ms / 1000.0 * sample_rate) if gap_duration_ms > 0 else 0
        )
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

        return ({"waveform": final_audio, "sample_rate": sample_rate},)

    def _trim_silence(self, audio_chunk, sample_rate, threshold):
        waveform = audio_chunk[0]  # (C, T)

        if waveform.shape[-1] == 0:
            return audio_chunk

        frame_size = 1024
        hop_size = 512

        padded = torch.nn.functional.pad(
            waveform, (0, frame_size - 1), mode="constant", value=0
        )

        n_frames = (padded.shape[-1] - frame_size) // hop_size + 1
        frames = []
        for j in range(n_frames):
            frame = padded[..., j * hop_size : j * hop_size + frame_size]
            frames.append(frame)

        if not frames:
            return audio_chunk

        rms_values = []
        for frame in frames:
            rms = torch.sqrt(torch.mean(frame**2, dim=-1)).mean()
            rms_values.append(rms.item())

        rms_values = np.array(rms_values)
        above_threshold = np.where(rms_values >= threshold)[0]

        if len(above_threshold) == 0:
            return torch.zeros(
                (1, waveform.shape[0], 1),
                dtype=waveform.dtype,
                device=waveform.device,
            )

        last_frame_idx = above_threshold[-1]
        trim_sample = (last_frame_idx + 1) * hop_size + frame_size
        trim_sample = min(trim_sample, waveform.shape[-1])

        trimmed = waveform[..., :trim_sample]
        return trimmed.unsqueeze(0)
