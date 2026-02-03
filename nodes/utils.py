import os
import re
import socket
import time

import comfy.modelmanagement


class TextTokens:
    def __init__(self):
        self.customtokens = {}
        self.tokens = {
            "time": str(time.time()).replace(".", ""),
            "hostname": socket.gethname(),
            "cuda:device": str(comfy.modelmanagement.get_torch_device()),
            "cuda:name": str(
                comfy.modelmanagement.get_torch_device_name(
                    device=comfy.modelmanagement.get_torch_device()
                )
            ),
        }

        if "." in self.tokens["time"]:
            self.tokens["time"] = self.tokens["time"].split(".")[0]

        try:
            self.tokens["user"] = os.getlogin() if os.getlogin() else "null"
        except Exception:
            self.tokens["user"] = "null"

    def addToken(self, name, value):
        self.customtokens[name] = value

    def removeToken(self, name):
        self.customtokens.pop(name, None)

    def formattime(self, formatcode):
        return time.strftime(formatcode, time.localtime(time.time()))

    def parseTokens(self, text: str) -> str:
        tokens = self.tokens.copy()
        if self.customtokens:
            tokens.update(self.customtokens)

        # Built-in tokens (no persistence)
        tokens["time"] = str(time.time())
        if "." in tokens["time"]:
            tokens["time"] = tokens["time"].split(".")[0]

        # Update time on each call
        for token, value in tokens.items():
            if token.startswith("time:"):
                continue
            pattern = re.compile(re.escape(f"{{{token}}}"))
            text = pattern.sub(value, text)

        # Simple tokens
        def replace_custom_time(match):
            formatcode = match.group(1)
            return self.formattime(formatcode)

        text = re.sub(r"\{time:(.*?)\}", replace_custom_time, text)

        return text  # {time:%Y-%m-%d_%H-%M-%S} style tokens


class cstr(str):
    """Colored string for terminal output"""

    class color:
        END = "\33[0m"
        BOLD = "\33[1m"
        ITALIC = "\33[3m"
        UNDERLINE = "\33[4m"
        BLINK = "\33[5m"
        BLINK2 = "\33[6m"
        SELECTED = "\33[7m"

        BLACK = "\33[30m"
        RED = "\33[31m"
        GREEN = "\33[32m"
        YELLOW = "\33[33m"
        BLUE = "\33[34m"
        VIOLET = "\33[35m"
        BEIGE = "\33[36m"
        WHITE = "\33[37m"

        GREY = "\33[90m"
        LIGHTRED = "\33[91m"
        LIGHTGREEN = "\33[92m"
        LIGHTYELLOW = "\33[93m"
        LIGHTBLUE = "\33[94m"
        LIGHTVIOLET = "\33[95m"
        LIGHTBEIGE = "\33[96m"
        LIGHTWHITE = "\33[97m"

    def __new__(cls, text):
        return super().__new__(cls, text)

    def __getattr__(self, attr):
        if attr.lower().startswith("_cstr"):
            attr = attr[6:]

        if hasattr(self.color, attr.upper()):
            return self.__class__(
                getattr(self.color, attr.upper()) + self + self.color.END
            )
        elif attr == "print":
            print(self)
            return self
        else:
            raise AttributeError(f"'cstr' object has no attribute '{attr}'")

    def __repr__(self):
        return f"cstr({super().__repr__()})"
