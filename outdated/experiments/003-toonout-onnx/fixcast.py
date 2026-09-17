# convert_float_to_float16 leaves pre-existing Cast(to=FLOAT) nodes typed
# fp32 while converting their consumers — rewrite them to FLOAT16, except
# casts feeding actual graph outputs (the keep_io_types boundary).
import numpy as np, onnx, onnxruntime as ort
from onnx import TensorProto

m = onnx.load("out/birefnet-toonout-fp16.onnx")
outs = {o.name for o in m.graph.output}
fixed = 0
for node in m.graph.node:
    if node.op_type == "Cast" and not (set(node.output) & outs) and "_input_cast" not in node.name and "_output_cast" not in node.name:
        for a in node.attribute:
            if a.name == "to" and a.i == TensorProto.FLOAT:
                a.i = TensorProto.FLOAT16
                fixed += 1
print("casts rewritten:", fixed)
onnx.save(m, "out/birefnet-toonout-fp16.onnx")

x = np.random.randn(1, 3, 1024, 1024).astype(np.float32)
a = ort.InferenceSession("out/birefnet-toonout.onnx", providers=["CPUExecutionProvider"]).run(None, {"image": x})[0]
b = ort.InferenceSession("out/birefnet-toonout-fp16.onnx", providers=["CPUExecutionProvider"]).run(None, {"image": x})[0]
print("fp32 vs fp16: max abs diff", float(np.abs(a - b).max()), "mean", float(np.abs(a - b).mean()))
