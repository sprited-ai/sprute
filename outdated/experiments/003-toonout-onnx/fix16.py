# Redo the fp16 conversion from the existing fp32 export. Shape inference
# first — without it the converter mistypes pre-existing Cast nodes
# ("Type (tensor(float16)) of output arg ... does not match expected float").
import os
import onnx
from onnx import shape_inference
from onnxconverter_common import float16

OUT = os.path.join(os.path.dirname(__file__), "out")
m = onnx.load(os.path.join(OUT, "birefnet-toonout.onnx"))
m = shape_inference.infer_shapes(m)
m16 = float16.convert_float_to_float16(m, keep_io_types=True)
path = os.path.join(OUT, "birefnet-toonout-fp16.onnx")
onnx.save(m16, path)
print("fp16 written:", os.path.getsize(path) >> 20, "MB")
