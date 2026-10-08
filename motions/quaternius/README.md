# Quaternius motions

119 action clips from [Quaternius Universal Animation Library Pro](https://quaternius.itch.io/universal-animation-library), licensed under CC0 (see LICENSE.txt). The source pack's A_TPose reference pose is excluded.

Each GLB contains one animation with Quaternius's original skeleton, joint channels (including fingers), key times and interpolation. No retargeting or resampling is applied to these files. Sprute maps the Quaternius skeleton to Template-kun only when rendering. The source is the in-place Pro GLB; root-motion variants remain in assets/quaternius. Rendering currently transfers the major body joints at 24 fps, not finger animation. Source animations ending in `_Loop` repeat; other actions hold their final pose.

```sh
sprute character-animate output/0001.directions.png --motion quaternius/walk
sprute character-animate output/0001.directions.png --motion quaternius/dance
sprute character-animate output/0001.directions.png --motion quaternius/punch-jab
sprute preview motions/quaternius/walk.glb
```

See library.json for all clip names, source names, timing, loop flags, provenance, and hashes. Walking, dancing, and the jab were test-rendered on Template-kun; the remaining clips have structural validation but have not all been visually reviewed. Props referenced by actions (chairs, weapons, etc.) are not included.
