import { parseArgs } from 'node:util';
import wanGraph from './wan-animation-template.json';
import scailGraph from './scail-animation-template.json';
import { baseUrl } from './comfy-animation.js';

/** Read-only compatibility checks for the fixed planner profile, not a job submission. */
export async function checkAnimationServer(server: string, model: 'wan-animate' | 'scail2' = 'wan-animate') {
  if (!['wan-animate', 'scail2'].includes(model)) throw new Error('Unknown animation model');
  const graph = model === 'scail2' ? scailGraph : wanGraph;
  const base = baseUrl(server);
  const classes = [...new Set(Object.values(graph).map(node => node.class_type))];
  const schemas = new Map<string, any>();
  // Small per-node responses avoid downloading every installed node's metadata.
  for (const name of classes) {
    const response = await fetch(new URL(`object_info/${encodeURIComponent(name)}`, base), { redirect: 'error', signal: AbortSignal.timeout(30_000) });
    if (!response.ok) throw new Error(`Cannot inspect ${name}: HTTP ${response.status}. No jobs submitted.`);
    const data = await response.json() as Record<string, any>;
    schemas.set(name, data?.[name]);
  }
  const issues: { code: string; node: string; detail: string }[] = [];
  for (const name of classes) if (!schemas.get(name)) issues.push({ code: 'missing-node', node: name, detail: `Install a ComfyUI node providing ${name}` });
  for (const node of Object.values(graph)) {
    const schema = schemas.get(node.class_type);
    if (!schema) continue;
    if (!schema.input || typeof schema.input !== 'object') {
      if (!issues.some(i => i.node === node.class_type && i.code === 'invalid-schema')) issues.push({ code: 'invalid-schema', node: node.class_type, detail: 'Server did not provide input definitions' });
      continue;
    }
    const declared = { ...schema.input.required, ...schema.input.optional };
    // VHS exposes encoder-specific inputs under the selected format, not at top level.
    if (node.class_type === 'VHS_VideoCombine') {
      const format = graph['15'].inputs.format;
      const formats = declared.format;
      if (!Array.isArray(formats?.[0]) || !formats[0].includes(format)) issues.push({ code: 'missing-video-format', node: node.class_type, detail: `Server does not list ${format}` });
      const fields = formats?.[1]?.formats?.[format];
      if (Array.isArray(fields)) for (const field of fields) {
        if (Array.isArray(field) && typeof field[0] === 'string') declared[field[0]] = field.slice(1);
      }
    }
    for (const field of Object.keys(node.inputs)) {
      if (!(field in declared)) issues.push({ code: 'unsupported-input', node: node.class_type, detail: `Profile needs input ${field}` });
    }
    for (const field of Object.keys(schema.input.required ?? {})) {
      if (!(field in node.inputs)) issues.push({ code: 'new-required-input', node: node.class_type, detail: `Server requires input ${field}, absent from this profile` });
    }
  }
  for (const [id, field] of [['1','unet_name'],['3','clip_name'],['4','vae_name'],['5','clip_name']] as const) {
    const node = graph[id], schema = schemas.get(node.class_type);
    if (!schema?.input) continue;
    const options = schema.input.required?.[field]?.[0] ?? schema.input.optional?.[field]?.[0];
    const value = (node.inputs as Record<string, unknown>)[field];
    if (!Array.isArray(options)) issues.push({ code: 'model-list-unavailable', node: node.class_type, detail: `Cannot verify model ${value}` });
    else if (!options.includes(value)) issues.push({ code: 'missing-model', node: node.class_type, detail: `Model filename not listed: ${value}` });
  }
  return { version: 1, profile: model === 'scail2' ? 'scail2-unipc40-v1' : 'wan-animate2-distill-euler10-v1', server: base.href,
    compatibleNamesAndInputs: issues.length === 0, checkedNodeTypes: classes.length, checkedModelNames: 4, issues,
    limitations: ['Does not verify model file hashes or licenses', 'Does not check driver files or uploaded character references', 'Does not validate connection types, numeric ranges or all node options', 'Does not prove available GPU memory, successful execution or animation quality'], submittedJobs: 0 };
}

export async function runCheckAnimationServer(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { server: { type: 'string', default: 'http://127.0.0.1:8188' }, model: { type: 'string', default: 'wan-animate' } } });
  if (positionals.length) throw new Error('Usage: sprute check-animation-server --server http://127.0.0.1:8188 [--model scail2]');
  if (values.model !== 'wan-animate' && values.model !== 'scail2') throw new Error('--model must be wan-animate or scail2');
  const result = await checkAnimationServer(values.server!, values.model);
  console.log(JSON.stringify(result, null, 2));
  if (!result.compatibleNamesAndInputs) process.exitCode = 1;
}
