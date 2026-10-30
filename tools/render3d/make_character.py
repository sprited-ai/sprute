"""A machine character from words or a design, to game sprites: Codex draws it in a T-pose, TRELLIS.2 on gin makes the
textured mesh, animate_parts.py cuts, animates and renders it.

docs/spikes/3d-render.md, "One command". The body plan is the stubby's (head with an antenna, barrel body, two side
stubs, two feet), because animate_parts.py's cut and gait are; --prompt therefore describes the look, not the build.

    python tools/render3d/make_character.py OUT_DIR --name brassy --prompt "a brass diving-helmet robot with a porthole face"
    python tools/render3d/make_character.py OUT_DIR --name stubby --reference stubby-4-views.png
    python tools/render3d/make_character.py OUT_DIR --name stubby --drawing stubby-tpose.png   # skip Codex

writes OUT_DIR/<name>-tpose.png (the drawing), OUT_DIR/<name>.glb and animate_parts.py's sprites; the steps already
done are kept, so a rerun picks up where one stopped. Extra arguments after -- go to animate_parts.py.
"""
import argparse, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GIN = "gin"
GIN_DIR = "sprute-3d"
GIN_OUTPUT = "dev/ComfyUI/output"

BODY = """\
- the body plan, exactly: a round head on top with a thin antenna rising from its crown, ending in a small knob; a short
  neck; a round barrel body; two short stubby arms, one on each side of the barrel; two small feet under it
- in a T-pose: the two arms held straight out sideways, horizontal, away from the body; feet slightly apart
- head and body face the same way, the face centred on the front of the head, the head not turned
- three-quarter front view (the whole robot turned about 30 degrees to its left), whole body in frame, centred, small margin
- rendered as a clean 3D toy render: soft even studio light, no strong shadows, no reflections, no outline ink
- plain pure white background, no ground shadow, no text, square 1024x1024"""

FROM_PROMPT = """\
Use your image generation tool to draw ONE image of a small cartoon robot game character, for turning into a 3D model
with an image-to-3D model. The look: {prompt}.
{body}
Save the generated image as {file} in the current directory (copy it from wherever the tool writes it). Reply with just
the path."""

FROM_REFERENCE = """\
The attached image shows a small cartoon robot game character. Use your image generation tool to draw ONE new image of
this same robot, for turning into a 3D model with an image-to-3D model:
- the same design exactly: every part, colour and marking it has
{body}
Save the generated image as {file} in the current directory (copy it from wherever the tool writes it). Reply with just
the path."""


def run(command, **kwargs):
    print("+", " ".join(map(str, command)) if isinstance(command, list) else command, flush=True)
    return subprocess.run(command, check=True, **kwargs)


def draw(out, name, prompt, reference):
    drawing = out / f"{name}-tpose.png"
    text = (FROM_REFERENCE if reference else FROM_PROMPT).format(prompt=prompt, body=BODY, file=drawing.name)
    command = ["codex", "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(out)]
    if reference:
        command += ["-i", str(reference.resolve())]
    # -i takes several files, so the prompt goes on stdin
    run(command + ["-"], input=text.encode())
    if not drawing.exists():
        sys.exit(f"Codex wrote no {drawing}")
    return drawing


def mesh(drawing, out, name):
    glb = out / f"{name}.glb"
    run(["ssh", GIN, f"mkdir -p {GIN_DIR}"])
    run(["scp", "-q", str(drawing), str(HERE / "trellis_shape.py"), f"{GIN}:{GIN_DIR}/"])
    # behind any ComfyUI workflow already running on gin
    log = run(["ssh", GIN, f"cd {GIN_DIR} && while pgrep -f '[c]omfyui run-workflow' >/dev/null; do sleep 15; done && "
               f"python3 trellis_shape.py {drawing.name} {name} --textured"], capture_output=True, text=True).stdout
    print(log)
    saved = re.findall(r"^save (\S+) (\S+\.glb)$", log, re.M)
    if not saved:
        sys.exit("TRELLIS.2 saved no GLB")
    folder, file = saved[-1]
    run(["scp", "-q", f"{GIN}:{GIN_OUTPUT}/{folder}/{file}", str(glb)])
    return glb


def main():
    argv, extra = (sys.argv[1:], [])
    if "--" in argv:
        argv, extra = argv[:argv.index("--")], argv[argv.index("--") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--name", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="the robot's look, in the stubby's body plan")
    source.add_argument("--reference", type=Path, help="a design to redraw in a T-pose, such as four diagonal views")
    source.add_argument("--drawing", type=Path, help="a T-pose drawing already made")
    parser.add_argument("--clip", action="append", help="NAME:FRAMES, as animate_parts.py; idle:36 walk:8 run:8 by default")
    a = parser.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    drawing = a.out / f"{a.name}-tpose.png"
    if a.drawing and a.drawing.resolve() != drawing.resolve():
        shutil.copy(a.drawing, drawing)
    elif not drawing.exists():
        drawing = draw(a.out, a.name, a.prompt, a.reference)
    glb = a.out / f"{a.name}.glb"
    if not glb.exists():
        glb = mesh(drawing, a.out, a.name)
    clips = [f"--clip={c}" for c in a.clip or ("idle:36", "walk:8", "run:8")]
    run([sys.executable, str(HERE / "animate_parts.py"), str(glb), str(drawing), str(a.out), "--name", a.name, *clips, *extra])


if __name__ == "__main__":
    main()
