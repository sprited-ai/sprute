# Proposal: prompt-first CLI — Jin's raw notes

> Source notes for [`003-cli-prompt-first.md`](003-cli-prompt-first.md), which is
> the canonical, reconciled version. Kept here verbatim as the original input;
> where the two differ, 003 wins. (The first-run menu here — Replicate/Fal/Comfy —
> is superseded by 003's "two doors: Gemini BYOK + Sprited Cloud"; see the open
> provider question in [`005-byok-direction-from-mana-session.md`](005-byok-direction-from-mana-session.md).)

## The surface

```sh
npx sprute "a small forest fairy"           # generate using defaults
npx sprute generate "a small forest fairy"  # generate
npx sprute                                  # claude code like environment for sprite gen
npx sprute init                             # initializes config file, setup api keys
```

## FTU experience

First time user experience should mirror what you see in Claude Code.

```
Choose your API provider:

1. Replicate API key
2. Fal.ai API key
3. Comfy Org API key

Enter your selection: ___
```

And in the advanced section, it will have more options like providing ComfyUI server url and the authorization header.

We need to let them know the location of where we are storing this info (i.e. .env.local). If that is the case we have to let them know we are storing there and let me .gitignore it.

Either on ~/.sprute or current directory (sprute init의 경우는 이쪽에 속하겠지)

## Chat interface

그렇고 나면 prompt 엔터하는 창이 나오고 이미지 paste도 가능하고, 로컬한 파일 reference에 추가도 가능해. path주면. 근데 프롬트 프로세싱 스텝이 있어서 프롬트를 프로세싱헤서 NBP에 들어갈만한 것으로 만들 수 잇어야해.

그리고 보내면, 에이전트가 마치 답하듯 일을 하기 시작해. 그리고 나오는데로 보여줘.

그리고 fix step같은 그런것도 프로그레시브하게 알려주고, 리즈닝 스텝도 알려주고.

이미지는 일단 패쓰로 보여주고, 링크 클릭해서 이미지 보이도록.

토큰 소모와 유제지도 어느정도 보여주먼 좋겟어.

## AI experience

이제 여기서... claude code에서 sprute을 자유자제로 사용할 수 있어야해. codex가 사용할수도 있고.

이게 내가 아는 분야에서 조금 넘어가 있어. 좀 어려울 수도 있을 것 같아.

## Chat multishot

멀티샷으로 나온것을 고쳐달라고 한다거나 수도 잇어. 아니면 체크 해보라고 할 수도 있고.

