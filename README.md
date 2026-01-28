# ComfyUI-Irama-AudioToolkit

English

ComfyUI custom nodes for basic audio utilities:
- 

## 📋 Changelog

### 2026-01-25 - Initial commit
- Based on functionality from existing nodes, but enhanced for your pleasure.
- Audio Stitcher: can take a bunch of batch audio tensors output from TTS or similar and stitch them together, remove silence and add a consistent gap.
- Load Text File: Not only loads in the text content, but sends the file name across to make the output files easier to identify and match up.
- Save Audio: Node not only saves the audio passed in, but catches the filename from Load Text File so as to match up the output with the input.
- Speed Controller: Provides 3 modes for stretching audio, differetn levels of quality, none ideal, but this is a tough thing to do well.



## Installation

To use rubberband you will need to install it from https://breakfastquay.com/rubberband/ and add it to your path



## Acknowledgments

- The original ComfyUI Nodes that were enhanced, including a node from [WAS Node Suite](https://github.com/WASasquatch/was-node-suite-comfyui). Thank you!


## License

- This project is licensed under the **Apache License 2.0**.
- Model weights are subject to the [Qwen3-TTS License Agreement](https://github.com/QwenLM/Qwen3-TTS#License).
