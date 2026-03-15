import os
import re

from .utils import TextTokens, cstr


class IramaSaveTextFile:
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
                        "default": "./ComfyUI/output/{time:%Y-%m-%d}",
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
                "file_extension": ("STRING", {"default": ".srt"}),
                "encoding": ("STRING", {"default": "utf-8"}),
                "filename_suffix": ("STRING", {"default": ""}),
            },
        }

    OUTPUT_NODE = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "save_text_file"
    CATEGORY = "Irama Audio Toolkit"

    def save_text_file(
        self,
        text,
        path,
        filename_prefix="ComfyUI",
        filename_delimiter="_",
        filename_number_padding=4,
        base_file_name="",
        file_extension=".srt",
        encoding="utf-8",
        filename_suffix="",
    ):
        tokens = TextTokens()
        path = tokens.parseTokens(path)
        filename_prefix = tokens.parseTokens(filename_prefix)

        # If base_filename is provided, prepend it to filename_prefix
        if base_file_name:
            filename_prefix = base_file_name + filename_delimiter + filename_prefix

        if not os.path.exists(path):
            print(cstr(f"[The path {path} doesn't exist! Creating it...]").warning)
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                print(cstr(f"[The path {path} could not be created! Is there write access?]\n{e}").error)

        if not text.strip():
            print(cstr("[There is no text specified to save! Text is empty.]").error)

        delimiter = filename_delimiter
        number_padding = int(filename_number_padding)

        filename = self._generate_filename(
            path,
            filename_prefix,
            delimiter,
            number_padding,
            file_extension,
            filename_suffix,
        )
        filepath = os.path.join(path, filename)

        self._write_text_file(filepath, text, encoding)

        # Build the output info for API access
        # Strip leading "./" or ".\" from path if present
        subfolder = path
        if subfolder.startswith("./"):
            subfolder = subfolder[2:]
        elif subfolder.startswith(".\\"):
            subfolder = subfolder[2:]

        # Remove "ComfyUI/output/" prefix if present to match ComfyUI's output structure
        if subfolder.startswith("ComfyUI/output/"):
            subfolder = subfolder[15:]
        elif subfolder.startswith("ComfyUI\\output\\"):
            subfolder = subfolder[15:]

        return {
            "ui": {"string": [text]},
            "result": (text,),
            "outputs": {
                "text": [
                    {"filename": filename, "subfolder": subfolder, "type": "output"}
                ]
            },
        }

    def _generate_filename(
        self, path, prefix, delimiter, number_padding, extension, suffix
    ):
        if number_padding == 0:
            # Directly write the file, no whitelist/history checks
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

    def _write_text_file(self, file, content, encoding):
        try:
            with open(file, "w", encoding=encoding, newline="") as f:
                f.write(content)
        except OSError as e:
            raise OSError(f"Unable to save file `{file}`: {e}")
