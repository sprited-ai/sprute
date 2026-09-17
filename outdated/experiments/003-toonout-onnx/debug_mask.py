import numpy as np, onnxruntime as ort, cv2, os
img = cv2.imread("../../examples/lisa.spritesheet.png", cv2.IMREAD_UNCHANGED)
cell = img[:, :img.shape[1]//8]  # S cell, BGRA
bgr = cell[:, :, :3].astype(np.float32)
a = (cell[:, :, 3:4].astype(np.float32)) / 255.0
flat = bgr * a + 128.0 * (1 - a)  # composite on gray
rgb = cv2.cvtColor(flat.astype(np.uint8), cv2.COLOR_BGR2RGB)
x = cv2.resize(rgb, (1024, 1024)).astype(np.float32) / 255.0
mean = np.array([0.485, 0.456, 0.406]); std = np.array([0.229, 0.224, 0.225])
x = ((x - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)
sess = ort.InferenceSession("out/birefnet-toonout.onnx", providers=["CPUExecutionProvider"])
mask = sess.run(None, {"image": x})[0][0, 0]
print("mask stats:", mask.min(), mask.max(), mask.mean())
cv2.imwrite("out/debug-mask.png", (np.clip(mask, 0, 1) * 255).astype(np.uint8))
