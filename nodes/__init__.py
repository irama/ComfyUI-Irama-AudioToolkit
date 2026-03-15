from .audio_batch_stitcher import IramaAudioBatchStitcher
from .audio_speed_correction import IramaAudioSpeedCorrection
from .load_text_from_file import IramaLoadTextFromFile
from .save_audio import IramaSaveAudio, IramaSaveAudioMP3, IramaSaveAudioOpus
from .save_srt import IramaWhisperToSRTText
from .save_text_file import IramaSaveTextFile

NODE_CLASS_MAPPINGS = {
    "IramaAudioBatchStitcher": IramaAudioBatchStitcher,
    "IramaAudioSpeedCorrection": IramaAudioSpeedCorrection,
    "IramaLoadTextFromFile": IramaLoadTextFromFile,
    "IramaSaveAudio": IramaSaveAudio,
    "IramaSaveAudioMP3": IramaSaveAudioMP3,
    "IramaSaveAudioOpus": IramaSaveAudioOpus,
    "IramaSaveTextFile": IramaSaveTextFile,
    "IramaWhisperToSRTText": IramaWhisperToSRTText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IramaAudioBatchStitcher": "🎵 Irama Audio Batch Stitcher (trim silence + gap)",
    "IramaAudioSpeedCorrection": "⚡ Irama Audio Speed Correction",
    "IramaLoadTextFromFile": "📄 Irama Load Text From File",
    "IramaSaveAudio": "💾 Irama Save Audio (FLAC)",
    "IramaSaveAudioMP3": "💾 Irama Save Audio (MP3)",
    "IramaSaveAudioOpus": "💾 Irama Save Audio (Opus)",
    "IramaSaveTextFile": "💾 Irama Save Text File",
    "IramaWhisperToSRTText": "🎙 Irama Whisper to SRT Text",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "IramaAudioBatchStitcher",
    "IramaAudioSpeedCorrection",
    "IramaLoadTextFromFile",
    "IramaSaveAudio",
    "IramaSaveAudioMP3",
    "IramaSaveAudioOpus",
    "IramaSaveTextFile",
    "IramaWhisperToSRTText",
]
