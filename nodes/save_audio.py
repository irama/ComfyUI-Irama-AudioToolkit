from comfy_api.latest import io, ui


class IramaSaveAudio(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IramaSaveAudio",
            display_name="Irama Save Audio (FLAC)",
            category="Irama Audio Toolkit",
            inputs=[
                io.Audio.Input("audio"),
                io.String.Input("filename_prefix", default="audio/ComfyUI"),
                io.String.Input(
                    "base_file_name",
                    default="",
                    tooltip="Optional base filename (e.g. 'story01'). If set, it is prepended to filename_prefix.",
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_png_info],
            is_output_node=True,
        )

    @classmethod
    def execute(
        cls,
        audio,
        filename_prefix="audio/ComfyUI",
        base_file_name="",
        format="flac",
        **_,
    ) -> io.NodeOutput:
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix = filename_prefix + "/"
            filename_prefix = filename_prefix + base_file_name

        return io.NodeOutput(
            ui=ui.AudioSaveHelper.get_save_audio_ui(
                audio,
                filename_prefix=filename_prefix,
                cls=cls,
                format=format,
            )
        )


save_flac = IramaSaveAudio.execute


class IramaSaveAudioMP3(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IramaSaveAudioMP3",
            display_name="Irama Save Audio (MP3)",
            category="Irama Audio Toolkit",
            inputs=[
                io.Audio.Input("audio"),
                io.String.Input("filename_prefix", default="audio/ComfyUI"),
                io.String.Input(
                    "base_file_name",
                    default="",
                    tooltip="Optional base filename (e.g. 'story01'). If set, it is prepended to filename_prefix.",
                ),
                io.Combo.Input(
                    "quality",
                    options=["V0", "128k", "320k"],
                    default="V0",
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_png_info],
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
        **_,
    ) -> io.NodeOutput:
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix = filename_prefix + "/"
            filename_prefix = filename_prefix + base_file_name

        return io.NodeOutput(
            ui=ui.AudioSaveHelper.get_save_audio_ui(
                audio,
                filename_prefix=filename_prefix,
                cls=cls,
                format=format,
                quality=quality,
            )
        )


save_mp3 = IramaSaveAudioMP3.execute


class IramaSaveAudioOpus(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IramaSaveAudioOpus",
            display_name="Irama Save Audio (Opus)",
            category="Irama Audio Toolkit",
            inputs=[
                io.Audio.Input("audio"),
                io.String.Input("filename_prefix", default="audio/ComfyUI"),
                io.String.Input(
                    "base_file_name",
                    default="",
                    tooltip="Optional base filename (e.g. 'story01'). If set, it is prepended to filename_prefix.",
                ),
                io.Combo.Input(
                    "quality",
                    options=["64k", "96k", "128k", "192k", "320k"],
                    default="128k",
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_png_info],
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
        **_,
    ) -> io.NodeOutput:
        if base_file_name:
            if not filename_prefix.endswith("/"):
                filename_prefix = filename_prefix + "/"
            filename_prefix = filename_prefix + base_file_name

        return io.NodeOutput(
            ui=ui.AudioSaveHelper.get_save_audio_ui(
                audio,
                filename_prefix=filename_prefix,
                cls=cls,
                format=format,
                quality=quality,
            )
        )


save_opus = IramaSaveAudioOpus.execute
