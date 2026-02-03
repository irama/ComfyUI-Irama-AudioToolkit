import librosa
import numpy as np
import torch

try:
    import pyrubberband as pyrb

    HAS_PYRUBBERBAND = True
except ImportError:
    HAS_PYRUBBERBAND = False


class IramaAudioSpeedCorrection:
    """
    Change playback speed of AUDIO using librosa, Rubberband, or resample methods.

    - speed < 1.0: slower
    - speed > 1.0: faster

    backends:
    - librosa: phase-vocoder time-stretch
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
                        "tooltip": "Method: librosa (fast), rubberband (best quality, needs CLI), resample (natural slowdown via time-resampling).",
                    },
                ),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "apply_speed"
    CATEGORY = "Irama Audio Toolkit"

    def apply_speed(self, audio, speed, backend):
        waveform = audio["waveform"]
        sr = int(audio["sample_rate"])

        if speed == 1.0:
            return (audio,)

        speed = float(max(0.5, min(2.0, speed)))
        backend = str(backend).lower()

        if backend == "resample":
            return (self._apply_resample(waveform, sr, speed),)
        else:
            return (self._apply_timestretch(waveform, sr, speed, backend),)

    def _apply_timestretch(self, waveform, sr, speed, backend):
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
                            rbargs=["--formant", "--crisp", "5"],
                        )
                    except Exception as e:
                        print(
                            f"IramaAudioSpeedCorrection: Rubberband failed ({e}), falling back to librosa."
                        )
                        y_stretch = librosa.effects.time_stretch(y, rate=speed)
                else:
                    if backend == "rubberband" and not HAS_PYRUBBERBAND:
                        print(
                            "IramaAudioSpeedCorrection: pyrubberband not available, using librosa instead."
                        )
                    y_stretch = librosa.effects.time_stretch(y, rate=speed)

                chan_stretched.append(torch.from_numpy(y_stretch))

            maxlen = max(ch.size(0) for ch in chan_stretched)
            chan_padded = []
            for ch in chan_stretched:
                if ch.size(0) < maxlen:
                    pad = torch.zeros(maxlen - ch.size(0), dtype=ch.dtype)
                    ch = torch.cat([ch, pad], dim=0)
                chan_padded.append(ch.unsqueeze(0))

            chan_tensor = torch.cat(chan_padded, dim=0)
            stretched_list.append(chan_tensor.unsqueeze(0))

        final_waveform = torch.cat(stretched_list, dim=0)

        return {
            "waveform": final_waveform.to(waveform.device),
            "sample_rate": sr,
        }

    def _apply_resample(self, waveform, sr, speed):
        """
        Resample in time: change number of samples so that speed semantics match:
        - speed < 1.0: slower (more samples)
        - speed > 1.0: faster (fewer samples)
        """
        b, c, t = waveform.shape

        speed = float(max(0.5, min(2.0, speed)))

        if speed == 1.0:
            return {"waveform": waveform, "sample_rate": sr}

        new_length = int(t / speed)

        resampled_list = []
        for bi in range(b):
            chan_resampled = []
            for ci in range(c):
                y = waveform[bi, ci].detach().cpu().numpy().astype(np.float32)

                if y.ndim != 1:
                    y = y.reshape(-1)

                try:
                    y_resampled = librosa.resample(y, orig_sr=t, target_sr=new_length)
                    chan_resampled.append(torch.from_numpy(y_resampled))
                except Exception as e:
                    print(
                        f"IramaAudioSpeedCorrection: resample (time-resample) failed ({e}), using original."
                    )
                    chan_resampled.append(torch.from_numpy(y))

            maxlen = max(ch.size(0) for ch in chan_resampled)
            chan_padded = []
            for ch in chan_resampled:
                if ch.size(0) < maxlen:
                    pad = torch.zeros(maxlen - ch.size(0), dtype=ch.dtype)
                    ch = torch.cat([ch, pad], dim=0)
                chan_padded.append(ch.unsqueeze(0))

            chan_tensor = torch.cat(chan_padded, dim=0)
            resampled_list.append(chan_tensor.unsqueeze(0))

        final_waveform = torch.cat(resampled_list, dim=0)

        return {
            "waveform": final_waveform.to(waveform.device),
            "sample_rate": sr,
        }
