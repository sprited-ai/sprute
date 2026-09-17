# sprute

**Make your own game character face 8 directions.**

Start with a character picture, or describe one. sprute uses AI to draw it from
different angles and puts the results into one image for your game.

![A character turning to face eight directions](https://raw.githubusercontent.com/sprited-ai/sprute/main/examples/monet.turntable.webp)

## Make a character

You need a computer with Node.js and npm installed, plus a Replicate API token
(a key that lets sprute use the AI). **The tool is open source, but AI generation
costs money through your Replicate account.**

### 1. Connect the AI

Open your computer's terminal—the app where you type commands. Paste this and
press Enter:

```sh
npx sprute login
```

Follow the instructions to add your API token. You only need to do this once.

### 2. Describe your character

```sh
npx sprute "a small forest fairy with green wings"
```

Replace the words inside the quotes with your own idea!

Already have a drawing? Use its file path instead:

```sh
npx sprute -r ./character.png
```

Here, `./character.png` means a picture named `character.png` in the folder
where you're running the command.

### 3. Find your pictures

Open the `outputs` folder in that same folder. Look for:

- **`.spritesheet.png`** — your character facing 8 directions, with no background.
- **`.turntable.webp`** — a moving preview like the one above.

![Eight character views in one image](https://raw.githubusercontent.com/sprited-ai/sprute/main/examples/monet.spritesheet.png)

These are standing poses, not a walking animation. AI can make mistakes, so
some pictures may need touching up. Left and right views are mirrored, which
can switch the side of a sword or other detail.

[More examples](examples/) · [Setup details and advanced options](docs/guide.md)

## Make it walk — experimental

Sprute 1.0 can turn your standing character into an eight-direction
walking animation, with a transparent sprite sheet and a browser preview:

```sh
node dist/cli.js animate outputs/my-character.spritesheet.png --wait
```

This needs a configured ComfyUI animation server and is **experimental in 1.0**.
[Set up walking once](docs/walking-setup.md) · [Make a walk and try it in Godot](docs/walking.md).
The server setup still needs technical help; the everyday command is one line.

[Current experiments and development tools](docs/animation-development.md).

Made by [Sprited](https://spritedx.com). Code and templates are [MIT licensed](LICENSE).
The character shown here is Monet; her pictures are for demonstration only,
so please make your own character for your game.
