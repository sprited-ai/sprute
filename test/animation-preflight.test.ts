import { test, expect } from 'vitest';
import { createServer } from 'node:http';
import { once } from 'node:events';
import wanGraph from '../src/node/wan-animation-template.json';
import scailGraph from '../src/node/scail-animation-template.json';
import { checkAnimationServer } from '../src/node/animation-preflight.js';

test.each(['wan-animate','scail2'] as const)('%s server check reports missing nodes/models/schema changes and performs only GETs', async (model) => {
  const graph = model === 'scail2' ? scailGraph : wanGraph;
  const schemas: Record<string, any> = {};
  for (const node of Object.values(graph)) {
    schemas[node.class_type] ??= {input:{required:{}}};
    for (const [key,value] of Object.entries(node.inputs)) schemas[node.class_type].input.required[key]=['ANY'];
  }
  schemas.UNETLoader.input.required.unet_name=[[graph['1'].inputs.unet_name]];
  schemas.CLIPLoader.input.required.clip_name=[[graph['3'].inputs.clip_name]];
  schemas.VAELoader.input.required.vae_name=[[graph['4'].inputs.vae_name]];
  schemas.CLIPVisionLoader.input.required.clip_name=[[graph['5'].inputs.clip_name]];
  const vhs = schemas.VHS_VideoCombine.input.required;
  for (const key of ['pix_fmt','crf','save_metadata','trim_to_audio']) delete vhs[key];
  vhs.format = [['video/h264-mp4'], {formats:{'video/h264-mp4':[
    ['pix_fmt',['yuv420p']],['crf','INT'],['save_metadata','BOOLEAN'],['trim_to_audio','BOOLEAN']
  ]}}];
  const methods: string[]=[];
  const server=createServer((req,res)=>{
    methods.push(req.method!);
    const name=decodeURIComponent(req.url!.split('/').pop()!);
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify(schemas[name]?{[name]:schemas[name]}:{}));
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');
  const url=`http://127.0.0.1:${(server.address() as any).port}`;
  try {
    const passing = await checkAnimationServer(url,model);
    expect(passing.compatibleNamesAndInputs).toBe(true);
    expect(passing.profile).toBe(model === 'scail2' ? 'scail2-unipc40-v1' : 'wan-animate2-distill-euler10-v1');
    delete schemas[model === 'scail2' ? 'WanSCAILToVideo' : 'WanAnimate2ToVideo'];
    schemas.UNETLoader.input.required.unet_name=[['different.safetensors']];
    delete schemas.KSampler.input.required.steps;
    schemas.VAELoader.input.required.new_setting=['STRING'];
    const result=await checkAnimationServer(url,model);
    expect(result.compatibleNamesAndInputs).toBe(false);
    expect(result.issues.map(i=>i.code)).toEqual(expect.arrayContaining(['missing-node','missing-model','unsupported-input','new-required-input']));
    expect(result.submittedJobs).toBe(0);
    expect(new Set(methods)).toEqual(new Set(['GET']));
  } finally {server.close();await once(server,'close');}
});
