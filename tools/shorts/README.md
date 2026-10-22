# Sprute Shorts

Spiky "streams" a real `sprute` run: the command typed, its output fast-forwarded, then the sprite it made.

1. Record a run on gin as an asciicast: `python3 record.py out.cast 44 24 -- sprute animate character --character mia --motion walk`. Copy the cast and the animation into `media/` (gitignored).
2. Turn the animation into an atlas: `python3 atlas.py media/mia.walk.webp media/mia.walk.png`. Put its frame count and seconds in the episode.
3. Write an episode in `eps/`. `stage` sets the typed command and the timing; `lines` are Spiky's lines, as in materia.
4. Render 60 fps frames: `node shoot.mjs eps/<ep>.json <framesDir>`.
5. Add the voice and Spiky's overlay with materia's compositor: `python3 ~/dev/materia/tools/shorts/compose.py eps/<ep>.json <framesDir> out.mp4`.

Pick a character whose animation is already known to be clean, and show Jin the video before posting.
