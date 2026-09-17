import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/cli.ts", "src/core/index.ts", "src/node/build.ts", "src/node/toonout.ts", "src/web/toonout.ts", "src/web/build.ts"],
  format: "esm",
  dts: true,
  clean: true,
  // tsup auto-externalizes dependencies and peerDependencies but NOT
  // optionalDependencies: onnxruntime-node got bundled into the published
  // dist with its .node binding loader paths broken, so import() threw and
  // the CLI silently fell back to Replicate matting. Keep both runtimes
  // external — they must resolve from node_modules at run time.
  external: ["onnxruntime-node", "onnxruntime-web"],
});
