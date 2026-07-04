import json

try:
    with open('models/voices-v1.0.bin', 'rb') as f:
        # voices.bin in kokoro-onnx is actually just a json file containing the voice tensors or parameters
        # Wait, it might be a binary file. Let's try loading it with python.
        # It's better to just use kokoro-onnx library to list voices if possible.
        pass
except Exception as e:
    pass

import onnxruntime
import kokoro_onnx

print("Loaded modules.")
