#!/usr/bin/env bash
# Generate a fighter with sprute and add it to the brawler's roster.
# Run from the sprute repo root, on a machine where `sprute setup` has run.
#
#   examples/brawler/make_character.sh knight "a knight in silver armor"
#
# The first character in characters/characters.json is the player; every one
# after it joins the enemy gang.
set -euo pipefail

name=${1:?usage: make_character.sh <name> [prompt]}
prompt=${2:-}

# The sprute motions pack.py reads (its MOTIONS table), all from the Quaternius library.
motions=quaternius/idle,quaternius/walk,quaternius/jog-fwd,quaternius/punch-jab,quaternius/kick,quaternius/hit-chest,quaternius/death01,quaternius/celebration

# sprute renames a taken name (knight -> knight-2), which pack.py would not find.
if [[ -e "output/$name.character.png" ]]; then
  echo "output/$name.character.png exists; pick another name" >&2
  exit 1
fi

sprute create character --name "$name" ${prompt:+--prompt "$prompt"} --motions "$motions" --no-preview
python examples/brawler/pack.py output --name "$name"
