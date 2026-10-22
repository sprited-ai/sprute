# Sprite viewer

Shows sprute characters in all eight directions, one motion at a time. Live at https://sprited-ai.github.io/sprute/examples/sprites/.

The viewer shows the characters in `characters/` first, then the brawler's cast from `../brawler/characters/`. Character `0018` was animated with sprute's bundled idle, walk and run and the Quaternius `punch-jab`, `jump` and `interact` clips.

## Add a character

Pack its animation strips with the brawler's packer, naming the motions to include:

```bash
python examples/brawler/pack.py output --name 0018 --out examples/sprites/characters \
  --motions idle=idle,walk=walk,run=run,punch=punch-jab,jump=jump,act=interact
```

## Run locally

```bash
python3 -m http.server 8765 --directory examples
```

Open http://localhost:8765/sprites/.
