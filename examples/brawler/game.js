// Sprute Brawl: a top-down arena brawler whose fighters are sprute characters.
// Every sprite comes from `pack.py`: one atlas per motion, a row per direction
// (S, SE, E, NE, N, NW, W, SW) and a column per frame.

const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const ARENA = { w: 1400, h: 900 };
const PLAYER = { hp: 100, run: 210, walk: 95 };
const ATTACKS = {
  // `at` is when in the motion the blow lands, as a fraction of its length.
  punch: { damage: 10, range: 70, at: 0.4, knock: 160, shake: 3 },
  kick: { damage: 20, range: 85, at: 0.5, knock: 340, shake: 7 },
};
const HIT_STUN = 0.35;
// Playback speed per motion. Mocap punches are realistic, which reads as slow in a game.
const RATE = { punch: 1.7, kick: 1.5 };
const CORPSE_TIME = 2.5;

// ---------------------------------------------------------------- loading

async function loadCharacter(id) {
  const base = `characters/${id}/`;
  const manifest = await (await fetch(base + "manifest.json")).json();
  const sheets = {};
  await Promise.all(Object.entries(manifest.motions).map(async ([motion, info]) => {
    const image = new Image();
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error(`could not load ${base + info.file}`));
      image.src = base + info.file;
    });
    sheets[motion] = { ...info, image };
  }));
  return { id, cell: manifest.cell, anchor: manifest.anchor, fps: manifest.fps, sheets };
}

// A recoloured copy of a character, so one sprute character can field a whole
// gang. With more characters in the roster, enemies use those as they are.
function tinted(character, degrees) {
  const angle = degrees * Math.PI / 180, c = Math.cos(angle), s = Math.sin(angle);
  // Hue rotation matrix (same as CSS hue-rotate), done on pixels once at load.
  const m = [
    0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928,
    0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283,
    0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072,
  ];
  const sheets = {};
  for (const [motion, sheet] of Object.entries(character.sheets)) {
    const out = document.createElement("canvas");
    out.width = sheet.image.width;
    out.height = sheet.image.height;
    const g = out.getContext("2d");
    g.drawImage(sheet.image, 0, 0);
    const pixels = g.getImageData(0, 0, out.width, out.height);
    const d = pixels.data;
    for (let i = 0; i < d.length; i += 4) {
      if (!d[i + 3]) continue;
      const r = d[i], gr = d[i + 1], b = d[i + 2];
      d[i] = m[0] * r + m[1] * gr + m[2] * b;
      d[i + 1] = m[3] * r + m[4] * gr + m[5] * b;
      d[i + 2] = m[6] * r + m[7] * gr + m[8] * b;
    }
    g.putImageData(pixels, 0, 0);
    sheets[motion] = { ...sheet, image: out };
  }
  return { ...character, id: `${character.id}@${degrees}`, sheets };
}

// ---------------------------------------------------------------- fighters

// Direction index from a vector, in sprute's order: S=0, SE, E, NE, N, NW, W, SW.
const directionOf = (dx, dy) => ((Math.round(Math.atan2(dx, dy) / (Math.PI / 4)) % 8) + 8) % 8;
const facingVector = (dir) => [Math.sin(dir * Math.PI / 4), Math.cos(dir * Math.PI / 4)];

function fighter(character, x, y, team, hp) {
  return {
    character, x, y, team, hp, maxHp: hp,
    vx: 0, vy: 0, dir: 0, state: "idle", t: 0, landed: false,
    flash: 0, cooldown: 0, gone: 0, power: 1,
  };
}

function setState(f, state) {
  if (f.state === state) return;
  f.state = state;
  f.t = 0;
  f.landed = false;
}

const sheetOf = (f) => f.character.sheets[f.state];
const fpsOf = (f) => f.character.fps * (RATE[f.state] || 1);
const lengthOf = (f) => sheetOf(f).frames / fpsOf(f);
const busy = (f) => ["punch", "kick", "hit", "death"].includes(f.state) && !(f.state !== "death" && f.t >= lengthOf(f));
const alive = (f) => f.state !== "death";

function frameOf(f) {
  const sheet = sheetOf(f);
  const frame = Math.floor(f.t * fpsOf(f));
  return sheet.loop ? frame % sheet.frames : Math.min(frame, sheet.frames - 1);
}

function attack(f, kind) {
  if (busy(f) || !alive(f)) return;
  setState(f, kind);
}

function strike(f, others) {
  const blow = ATTACKS[f.state];
  if (!blow || f.landed || f.t < lengthOf(f) * blow.at) return;
  f.landed = true;
  const [fx, fy] = facingVector(f.dir);
  let struck = false;
  for (const o of others) {
    if (o.team === f.team || !alive(o)) continue;
    const dx = o.x - f.x, dy = o.y - f.y, dist = Math.hypot(dx, dy);
    if (dist > blow.range) continue;
    // In front: within ~65 degrees of where the attacker faces.
    if (dist > 12 && (dx * fx + dy * fy) / dist < 0.42) continue;
    hurt(o, blow, Math.round(blow.damage * f.power), dx / (dist || 1), dy / (dist || 1));
    struck = true;
  }
  if (struck) shake = Math.max(shake, blow.shake);
}

function hurt(f, blow, damage, nx, ny) {
  f.hp = Math.max(0, f.hp - damage);
  f.vx += nx * blow.knock;
  f.vy += ny * blow.knock;
  f.dir = directionOf(-nx, -ny);
  f.flash = 0.12;
  popups.push({ x: f.x, y: f.y - 110, text: String(damage), t: 0, kick: blow === ATTACKS.kick });
  for (let i = 0; i < 8; i++) {
    const a = Math.random() * Math.PI * 2, v = 80 + Math.random() * 160;
    sparks.push({ x: f.x - nx * 10, y: f.y - 60, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 60, t: 0 });
  }
  if (f.hp === 0) {
    setState(f, "death");
    if (f.team === "enemy") score++;
  } else {
    setState(f, "hit");
  }
}

// ---------------------------------------------------------------- game state

let roster = [];
let player, fighters, wave, score, mode, banner, shake, sparks, popups;
const keys = new Set();

function reset() {
  player = fighter(roster[0], ARENA.w / 2, ARENA.h / 2, "player", PLAYER.hp);
  fighters = [player];
  wave = 0;
  score = 0;
  shake = 0;
  sparks = [];
  popups = [];
  nextWave();
}

function nextWave() {
  wave++;
  banner = { text: `Wave ${wave}`, t: 0 };
  const count = Math.min(1 + wave, 9);
  const gang = roster.length > 1 ? roster.slice(1) : roster;
  for (let i = 0; i < count; i++) {
    // Spawn along the arena edge, away from the player.
    const side = Math.floor(Math.random() * 4);
    const along = Math.random();
    const x = side < 2 ? along * ARENA.w : side === 2 ? 40 : ARENA.w - 40;
    const y = side >= 2 ? along * ARENA.h : side === 0 ? 60 : ARENA.h - 20;
    const enemy = fighter(gang[i % gang.length], x, y, "enemy", 30 + wave * 6);
    enemy.speed = 70 + Math.min(wave, 8) * 8 + Math.random() * 20;
    enemy.cooldown = 0.6 + Math.random();
    // Enemies hit softer than the player, and harder each wave.
    enemy.power = Math.min(1, 0.35 + wave * 0.05);
    fighters.push(enemy);
  }
}

// ---------------------------------------------------------------- update

function controlPlayer(dt) {
  if (busy(player) || !alive(player)) return;
  let dx = 0, dy = 0;
  if (keys.has("ArrowLeft") || keys.has("KeyA")) dx--;
  if (keys.has("ArrowRight") || keys.has("KeyD")) dx++;
  if (keys.has("ArrowUp") || keys.has("KeyW")) dy--;
  if (keys.has("ArrowDown") || keys.has("KeyS")) dy++;
  if (mode === "between") return setState(player, "win");
  if (dx || dy) {
    const walking = keys.has("ShiftLeft") || keys.has("ShiftRight");
    const speed = walking ? PLAYER.walk : PLAYER.run;
    const n = Math.hypot(dx, dy);
    player.x += (dx / n) * speed * dt;
    player.y += (dy / n) * speed * dt;
    player.dir = directionOf(dx, dy);
    setState(player, walking ? "walk" : "run");
  } else {
    setState(player, "idle");
  }
}

function playerAttack(kind) {
  if (mode !== "play" || busy(player) || !alive(player)) return;
  // Aim assist: eight directions are coarse, so turn to a close enemy.
  let best = null, bestDist = 130;
  for (const f of fighters) {
    if (f.team !== "enemy" || !alive(f)) continue;
    const d = Math.hypot(f.x - player.x, f.y - player.y);
    if (d < bestDist) { best = f; bestDist = d; }
  }
  if (best) player.dir = directionOf(best.x - player.x, best.y - player.y);
  attack(player, kind);
}

function think(enemy, dt) {
  enemy.cooldown -= dt;
  if (busy(enemy) || !alive(enemy)) return;
  if (!alive(player)) return setState(enemy, "win");
  const dx = player.x - enemy.x, dy = player.y - enemy.y, dist = Math.hypot(dx, dy);
  enemy.dir = directionOf(dx, dy);
  if (dist < 62) {
    // Like any beat-em-up gang, they take turns: two swing at a time at most.
    const swinging = fighters.filter((o) => o.team === "enemy" && (o.state === "punch" || o.state === "kick")).length;
    if (enemy.cooldown <= 0 && swinging < 2) {
      attack(enemy, Math.random() < 0.3 ? "kick" : "punch");
      enemy.cooldown = 1.6 + Math.random() * 1.4 - Math.min(wave, 8) * 0.08;
    } else {
      setState(enemy, "idle");
    }
    return;
  }
  // Keep some space from the rest of the gang so they surround the player.
  let sx = 0, sy = 0;
  for (const o of fighters) {
    if (o === enemy || o.team !== "enemy" || !alive(o)) continue;
    const ox = enemy.x - o.x, oy = enemy.y - o.y, d = Math.hypot(ox, oy);
    if (d > 0 && d < 70) { sx += ox / d; sy += oy / d; }
  }
  const mx = dx / dist + sx * 0.8, my = dy / dist + sy * 0.8, n = Math.hypot(mx, my) || 1;
  const running = dist > 320;
  const speed = enemy.speed * (running ? 1.8 : 1);
  enemy.x += (mx / n) * speed * dt;
  enemy.y += (my / n) * speed * dt;
  setState(enemy, running ? "run" : "walk");
}

function update(dt) {
  if (mode === "title") return;
  if (banner) banner.t += dt;
  // The break between waves runs on game time, so a paused tab stays paused.
  if (mode === "between" && banner.next && banner.t > 2.6) { mode = "play"; nextWave(); }
  controlPlayer(dt);
  for (const f of fighters) if (f.team === "enemy") think(f, dt);
  for (const f of fighters) {
    f.t += dt;
    f.flash = Math.max(0, f.flash - dt);
    strike(f, fighters);
    // Knockback slides and dies down.
    f.x += f.vx * dt;
    f.y += f.vy * dt;
    const friction = Math.exp(-dt * 9);
    f.vx *= friction;
    f.vy *= friction;
    f.x = Math.max(30, Math.min(ARENA.w - 30, f.x));
    f.y = Math.max(50, Math.min(ARENA.h - 10, f.y));
    if (f.state === "hit" && f.t >= Math.max(lengthOf(f), HIT_STUN)) setState(f, "idle");
    if ((f.state === "punch" || f.state === "kick") && f.t >= lengthOf(f)) setState(f, "idle");
    if (f.state === "death" && f.t > lengthOf(f)) f.gone += dt;
  }
  fighters = fighters.filter((f) => f === player || f.gone < CORPSE_TIME);

  for (const s of sparks) { s.t += dt; s.x += s.vx * dt; s.y += s.vy * dt; s.vy += 500 * dt; }
  sparks = sparks.filter((s) => s.t < 0.4);
  for (const p of popups) p.t += dt;
  popups = popups.filter((p) => p.t < 0.8);
  shake = Math.max(0, shake - dt * 30);

  if (mode === "play" && !alive(player)) {
    mode = "over";
    banner = { text: "K.O.", t: 0 };
  }
  const enemiesLeft = fighters.some((f) => f.team === "enemy" && alive(f));
  if (mode === "play" && !enemiesLeft) {
    mode = "between";
    banner = { text: `Wave ${wave} cleared`, t: 0 };
    player.hp = Math.min(player.maxHp, player.hp + 25);
    banner.next = true;
  }
}

// ---------------------------------------------------------------- drawing

let ground;
function makeGround() {
  ground = document.createElement("canvas");
  ground.width = ARENA.w + 400;
  ground.height = ARENA.h + 400;
  const g = ground.getContext("2d");
  g.fillStyle = "#2b3a22";
  g.fillRect(0, 0, ground.width, ground.height);
  // Grass flecks outside the ring.
  for (let i = 0; i < 2500; i++) {
    g.fillStyle = `hsla(${85 + Math.random() * 30}, 35%, ${18 + Math.random() * 14}%, 0.8)`;
    g.fillRect(Math.random() * ground.width, Math.random() * ground.height, 2, 3 + Math.random() * 4);
  }
  // Flagstone floor.
  const tile = 70;
  for (let y = 0; y < ARENA.h; y += tile) {
    for (let x = 0; x < ARENA.w; x += tile) {
      const light = 34 + Math.random() * 8 + ((x / tile + y / tile) % 2) * 3;
      g.fillStyle = `hsl(30, 12%, ${light}%)`;
      g.fillRect(200 + x + 1, 200 + y + 1, tile - 2, tile - 2);
    }
  }
  g.strokeStyle = "#1a1512";
  g.lineWidth = 8;
  g.strokeRect(196, 196, ARENA.w + 8, ARENA.h + 8);
}

function drawFighter(f) {
  const { cell, anchor } = f.character;
  const sheet = sheetOf(f);
  const alpha = f.gone ? Math.max(0, 1 - f.gone / CORPSE_TIME) : 1;
  ctx.globalAlpha = alpha * 0.35;
  ctx.fillStyle = "#000";
  ctx.beginPath();
  ctx.ellipse(f.x, f.y, 26, 9, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = alpha;
  const sx = frameOf(f) * cell[0], sy = f.dir * cell[1];
  const dx = Math.round(f.x - anchor[0]), dy = Math.round(f.y - anchor[1]);
  ctx.drawImage(sheet.image, sx, sy, cell[0], cell[1], dx, dy, cell[0], cell[1]);
  if (f.flash > 0) {
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = f.flash / 0.12 * 0.7;
    ctx.drawImage(sheet.image, sx, sy, cell[0], cell[1], dx, dy, cell[0], cell[1]);
    ctx.globalCompositeOperation = "source-over";
  }
  ctx.globalAlpha = 1;
  if (f.team === "enemy" && alive(f) && f.hp < f.maxHp) {
    const w = 44, top = f.y - anchor[1] + 8;
    ctx.fillStyle = "#0009";
    ctx.fillRect(f.x - w / 2 - 1, top - 1, w + 2, 6);
    ctx.fillStyle = "#e5484d";
    ctx.fillRect(f.x - w / 2, top, w * f.hp / f.maxHp, 4);
  }
}

function text(str, x, y, size, color = "#fff", align = "center") {
  ctx.font = `800 ${size}px ui-rounded, system-ui, sans-serif`;
  ctx.textAlign = align;
  ctx.lineWidth = Math.max(3, size / 7);
  ctx.strokeStyle = "#000c";
  ctx.strokeText(str, x, y);
  ctx.fillStyle = color;
  ctx.fillText(str, x, y);
}

function draw(time) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr;
    canvas.height = h * dpr;
  }
  const zoom = Math.max(0.7, Math.min(1.6, Math.min(w / 850, h / 560)));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#14110f";
  ctx.fillRect(0, 0, w, h);

  if (mode === "title") return drawTitle(w, h, time, zoom);

  // Camera follows the player, held inside the arena where it can be.
  const viewW = w / zoom, viewH = h / zoom;
  const clampCam = (v, view, size) => size + 200 < view ? size / 2 : Math.max(view / 2 - 100, Math.min(size + 100 - view / 2, v));
  const cx = clampCam(player.x, viewW, ARENA.w), cy = clampCam(player.y - 50, viewH, ARENA.h);
  const jitter = () => (Math.random() - 0.5) * shake;
  ctx.setTransform(dpr * zoom, 0, 0, dpr * zoom, dpr * (w / 2 - cx * zoom + jitter()), dpr * (h / 2 - cy * zoom + jitter()));
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(ground, -200, -200);

  // Corpses under the living, then everyone by depth.
  const order = [...fighters].sort((a, b) => (alive(a) - alive(b)) || a.y - b.y);
  for (const f of order) drawFighter(f);
  for (const s of sparks) {
    ctx.fillStyle = `rgba(255, ${200 - s.t * 300}, 80, ${1 - s.t / 0.4})`;
    ctx.fillRect(s.x - 3, s.y - 3, 6, 6);
  }
  for (const p of popups) {
    ctx.globalAlpha = 1 - p.t / 0.8;
    text(p.text, p.x, p.y - p.t * 50, p.kick ? 30 : 22, p.kick ? "#ffd84a" : "#fff");
    ctx.globalAlpha = 1;
  }

  // HUD in screen space.
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#000a";
  ctx.fillRect(20, 20, 260, 22);
  ctx.fillStyle = player.hp > 30 ? "#46a758" : "#e5484d";
  ctx.fillRect(23, 23, 254 * player.hp / player.maxHp, 16);
  text(`HP ${player.hp}`, 30, 37, 14, "#fff", "left");
  text(`Wave ${wave}   KOs ${score}`, w - 24, 40, 22, "#fff", "right");
  text("WASD move · Shift walk · J punch · K kick", w / 2, h - 18, 14, "#fffa");

  if (banner && (banner.t < 2.2 || mode === "over")) {
    const fade = mode === "over" ? 1 : Math.min(1, (2.2 - banner.t) * 3);
    ctx.globalAlpha = fade;
    text(banner.text, w / 2, h * 0.32, 64, mode === "over" ? "#e5484d" : "#ffd84a");
    if (mode === "over") text(`${score} KOs · press R to fight again`, w / 2, h * 0.32 + 48, 24);
    ctx.globalAlpha = 1;
  }
}

function drawTitle(w, h, time, zoom) {
  text("SPRUTE BRAWL", w / 2, h * 0.24, 72, "#ffd84a");
  text("Every fighter here was generated by sprute", w / 2, h * 0.24 + 40, 18, "#fffc");
  // The roster turns in place, showing off the eight directions.
  const gap = 130 * zoom;
  roster.forEach((character, i) => {
    const dir = Math.floor(time / 600 + i) % 8;
    const sheet = character.sheets.idle;
    const frame = Math.floor(time / 1000 * character.fps) % sheet.frames;
    const [cw, ch] = character.cell;
    const scale = 1.6 * zoom;
    const x = w / 2 + (i - (roster.length - 1) / 2) * gap - (cw * scale) / 2;
    ctx.drawImage(sheet.image, frame * cw, dir * ch, cw, ch, x, h * 0.36, cw * scale, ch * scale);
  });
  const pulse = 0.6 + 0.4 * Math.sin(time / 300);
  ctx.globalAlpha = pulse;
  text("Press Enter to fight", w / 2, h * 0.36 + 128 * 1.6 * zoom + 50, 30);
  ctx.globalAlpha = 1;
  text("WASD / arrows move · Shift walk · J punch · K kick", w / 2, h - 30, 16, "#fffa");
}

// ---------------------------------------------------------------- main

addEventListener("keydown", (e) => {
  keys.add(e.code);
  if (mode === "title" && (e.code === "Enter" || e.code === "Space")) { mode = "play"; reset(); }
  else if (e.code === "KeyJ" || e.code === "KeyZ") playerAttack("punch");
  else if (e.code === "KeyK" || e.code === "KeyX") playerAttack("kick");
  else if (e.code === "KeyR" && mode === "over") { mode = "play"; reset(); }
  if (e.code.startsWith("Arrow") || e.code === "Space") e.preventDefault();
});
addEventListener("keyup", (e) => keys.delete(e.code));
addEventListener("blur", () => keys.clear());

async function main() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const ids = await (await fetch("characters/characters.json")).json();
  roster = await Promise.all(ids.map(loadCharacter));
  // One character: field its recoloured twins as the gang.
  if (roster.length === 1) roster.push(tinted(roster[0], 150), tinted(roster[0], 260));
  makeGround();
  mode = "title";
  // ?debug: drive the simulation from the console or a test script.
  if (new URLSearchParams(location.search).has("debug")) {
    window.brawl = {
      step: (seconds, dt = 1 / 60) => { for (let t = 0; t < seconds; t += dt) update(dt); draw(performance.now()); },
      get state() { return { mode, wave, score, player, fighters }; },
    };
  }
  let last = performance.now();
  const frame = (now) => {
    update(Math.min(0.05, (now - last) / 1000));
    last = now;
    draw(now);
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

main().catch((error) => {
  console.error(error);
  ctx.fillStyle = "#fff";
  ctx.font = "16px system-ui";
  ctx.fillText(`Could not load characters: ${error.message}`, 20, 40);
  ctx.fillText("Serve this folder over http (python3 -m http.server) and run pack.py first.", 20, 64);
});
