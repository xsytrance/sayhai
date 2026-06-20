/* =============================================================================
 *  The Body.  Phase 0: a goofy face that is never perfectly still and can strike
 *  all 12 emotion poses with springy, overshooting motion.
 *
 *  The whole thing is driven by one idea: every moving part of the face is a
 *  spring with a target. An emotion is just a table of targets + a "springiness"
 *  profile. Switch emotion -> retarget the springs -> they jiggle to a stop.
 *  On top of that runs an idle loop (blinks, eye wander, breathing, twitches)
 *  so it's alive even when nothing is happening.
 * ========================================================================== */

(() => {
  "use strict";

  // ---- geometry (matches the SVG in face.html) ----------------------------
  const CX = 500, CY = 540;            // face center for the global transform
  const EYE_L = { x: 360, y: 470 };
  const EYE_R = { x: 640, y: 470 };
  const PUPIL_R = 66;
  const MX = 500, MY = 720;            // mouth center
  const GAZE_LIMIT = 60;               // how far the pupils can travel from center

  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------------------
  //  Spring — a tiny damped harmonic oscillator. Underdamped => overshoot.
  // ---------------------------------------------------------------------------
  class Spring {
    constructor(value, k = 175, c = 15) {
      this.value = value; this.target = value; this.v = 0; this.k = k; this.c = c;
    }
    profile(k, c) { this.k = k; this.c = c; return this; }
    to(t) { this.target = t; }
    snap(v) { if (v !== undefined) { this.value = v; this.target = v; } else this.value = this.target; this.v = 0; }
    kick(impulse) { this.v += impulse; }     // inject velocity for a reactive bounce
    step(h) {
      const a = -this.k * (this.value - this.target) - this.c * this.v;
      this.v += a * h;
      this.value += this.v * h;
    }
  }

  // springiness profiles: { stiffness k, damping c }. Lower c = more overshoot.
  const PROFILES = {
    bouncy: { k: 230, c: 11 },   // hyped, big jiggle
    happy:  { k: 210, c: 12 },
    normal: { k: 175, c: 15 },
    soft:   { k: 95,  c: 21 },   // droopy, slow
    stiff:  { k: 300, c: 27 },   // tense, snappy
    wobble: { k: 130, c: 7  },   // loose, dizzy
    think:  { k: 150, c: 17 },
  };

  // ---------------------------------------------------------------------------
  //  Springs for every degree of freedom. These get retargeted per emotion.
  // ---------------------------------------------------------------------------
  const S = {
    tilt: new Spring(0), ty: new Spring(0),
    sx: new Spring(1), sy: new Spring(1),
    eyeOpen: new Spring(1), lidAngle: new Spring(0), lowerLid: new Spring(0.05),
    pupilScale: new Spring(1),
    gazeX: new Spring(0), gazeY: new Spring(0),
    browLY: new Spring(-6), browRY: new Spring(-6),
    browLRot: new Spring(0), browRRot: new Spring(0),
    mW: new Spring(200), mOpen: new Spring(8), mCurve: new Spring(26), mAsym: new Spring(0),
    tuftSway: new Spring(0).profile(90, 7),
    // these aren't pose-profiled; they have their own feel:
    blink: new Spring(1).profile(900, 42),
    sacX: new Spring(0).profile(260, 20), sacY: new Spring(0).profile(260, 20),
    // overlay fades:
    blush: new Spring(0).profile(120, 18),
    heartPupil: new Spring(0).profile(120, 18), spiral: new Spring(0).profile(120, 18),
    fxHearts: new Spring(0).profile(120, 18), fxSparkles: new Spring(0).profile(120, 18),
    fxZzz: new Spring(0).profile(120, 18), fxSweat: new Spring(0).profile(120, 18),
    fxTears: new Spring(0).profile(120, 18), fxThink: new Spring(0).profile(120, 18),
  };
  // the springs that take on each emotion's profile (everything that defines a pose)
  const POSE_SPRINGS = ["tilt", "ty", "sx", "sy", "eyeOpen", "lidAngle", "lowerLid",
    "pupilScale", "gazeX", "gazeY", "browLY", "browRY", "browLRot", "browRRot",
    "mW", "mOpen", "mCurve", "mAsym"];

  // ---------------------------------------------------------------------------
  //  The poses. One row per emotion. This IS the emotion->face mapping.
  //  Sign conventions: browY/gazeY negative = up. browRot +/-: angry vs worried.
  //  lidAngle + = angry slant, - = sad slant. mCurve + = smile, - = frown.
  // ---------------------------------------------------------------------------
  const POSES = {
    neutral: { profile: "normal", tilt: 0, ty: 0, sx: 1, sy: 1, eyeOpen: 1, lidAngle: 0,
      lowerLid: 0.05, pupilScale: 1, gazeX: 0, gazeY: 0, browLY: -6, browRY: -6,
      browLRot: 0, browRRot: 0, mW: 200, mOpen: 8, mCurve: 26, mAsym: 0,
      breathRate: 1.6, breathAmp: 0.012, saccade: 1 },

    happy: { profile: "happy", tilt: 0, ty: -6, sx: 1.02, sy: 1.02, eyeOpen: 0.8, lidAngle: 0,
      lowerLid: 0.42, pupilScale: 1.05, gazeX: 0, gazeY: 0, browLY: -22, browRY: -22,
      browLRot: 0, browRRot: 0, mW: 300, mOpen: 70, mCurve: 60, mAsym: 0,
      breathRate: 2.0, breathAmp: 0.016, saccade: 1, blush: 0.35 },

    excited: { profile: "bouncy", tilt: 0, ty: -16, sx: 1.0, sy: 1.06, eyeOpen: 1.12, lidAngle: 0,
      lowerLid: 0.1, pupilScale: 1.3, gazeX: 0, gazeY: -6, browLY: -34, browRY: -34,
      browLRot: 0, browRRot: 0, mW: 320, mOpen: 120, mCurve: 70, mAsym: 0,
      breathRate: 2.8, breathAmp: 0.02, saccade: 0.8, blush: 0.3, sparkles: true },

    mischievous: { profile: "normal", tilt: -4, ty: 0, sx: 1.0, sy: 1.0, eyeOpen: 0.7, lidAngle: 0,
      lowerLid: 0.5, pupilScale: 0.95, gazeX: 22, gazeY: 8, browLY: -2, browRY: -28,
      browLRot: 6, browRRot: 6, mW: 250, mOpen: 26, mCurve: 34, mAsym: 30,
      breathRate: 1.7, breathAmp: 0.013, saccade: 0.7, blush: 0.1 },

    curious: { profile: "normal", tilt: 8, ty: 0, sx: 1, sy: 1, eyeOpen: 1.05, lidAngle: 0,
      lowerLid: 0.05, pupilScale: 1.1, gazeX: 16, gazeY: -6, browLY: -32, browRY: -6,
      browLRot: -6, browRRot: 0, mW: 150, mOpen: 30, mCurve: 10, mAsym: 6,
      breathRate: 1.7, breathAmp: 0.013, saccade: 0.9 },

    thinking: { profile: "think", tilt: 6, ty: 0, sx: 1, sy: 1, eyeOpen: 0.95, lidAngle: 0,
      lowerLid: 0.1, pupilScale: 0.9, gazeX: 26, gazeY: -26, browLY: -18, browRY: -4,
      browLRot: -4, browRRot: 2, mW: 150, mOpen: 12, mCurve: -4, mAsym: 14,
      breathRate: 1.5, breathAmp: 0.012, saccade: 0.4, think: true },

    surprised: { profile: "normal", tilt: 0, ty: -10, sx: 1.04, sy: 1.08, eyeOpen: 1.2, lidAngle: 0,
      lowerLid: 0, pupilScale: 1.25, gazeX: 0, gazeY: 0, browLY: -46, browRY: -46,
      browLRot: 0, browRRot: 0, mW: 150, mOpen: 130, mCurve: 0, mAsym: 0,
      breathRate: 2.2, breathAmp: 0.016, saccade: 0.3, sweat: true, kick: 9 },

    sad: { profile: "soft", tilt: -3, ty: 8, sx: 0.99, sy: 0.95, eyeOpen: 0.85, lidAngle: -16,
      lowerLid: 0.12, pupilScale: 1.05, gazeX: 0, gazeY: 22, browLY: -10, browRY: -10,
      browLRot: -10, browRRot: 10, mW: 200, mOpen: 16, mCurve: -34, mAsym: 0,
      breathRate: 1.2, breathAmp: 0.014, saccade: 0.5, tears: true },

    sleepy: { profile: "soft", tilt: 4, ty: 6, sx: 1.0, sy: 0.97, eyeOpen: 0.4, lidAngle: 2,
      lowerLid: 0.18, pupilScale: 0.95, gazeX: 0, gazeY: 12, browLY: 2, browRY: 2,
      browLRot: 0, browRRot: 0, mW: 170, mOpen: 24, mCurve: 6, mAsym: 8,
      breathRate: 0.9, breathAmp: 0.022, saccade: 0.3, zzz: true },

    grumpy: { profile: "stiff", tilt: 0, ty: 2, sx: 1.01, sy: 0.99, eyeOpen: 0.6, lidAngle: 16,
      lowerLid: 0.18, pupilScale: 0.75, gazeX: 0, gazeY: 0, browLY: 10, browRY: 10,
      browLRot: 14, browRRot: -14, mW: 220, mOpen: 14, mCurve: -30, mAsym: 0,
      breathRate: 1.8, breathAmp: 0.012, saccade: 0.6 },

    love: { profile: "bouncy", tilt: 0, ty: -6, sx: 1.02, sy: 1.03, eyeOpen: 0.95, lidAngle: 0,
      lowerLid: 0.3, pupilScale: 1.4, gazeX: 0, gazeY: 0, browLY: -24, browRY: -24,
      browLRot: 0, browRRot: 0, mW: 280, mOpen: 60, mCurve: 58, mAsym: 0,
      breathRate: 2.0, breathAmp: 0.016, saccade: 0.5, blush: 0.85, hearts: true, heartPupil: true },

    dizzy: { profile: "wobble", tilt: 0, ty: 0, sx: 1.0, sy: 1.0, eyeOpen: 1.0, lidAngle: 0,
      lowerLid: 0.05, pupilScale: 1.0, gazeX: 0, gazeY: 0, browLY: -8, browRY: -8,
      browLRot: 0, browRRot: 0, mW: 220, mOpen: 60, mCurve: -6, mAsym: 0,
      breathRate: 2.0, breathAmp: 0.02, saccade: 0, spiral: true },
  };
  const EMO_ORDER = Object.keys(POSES);

  // ---------------------------------------------------------------------------
  //  Path builders
  // ---------------------------------------------------------------------------
  function mouthPath(w, open, curve, asym) {
    const half = w / 2;
    const lx = MX - half, rx = MX + half;
    const cyl = MY - curve - asym;          // left corner
    const cyr = MY - curve + asym;          // right corner
    const upMid = MY + open * 0.06;         // upper lip mid
    const loMid = MY + open * 0.95 + 10;    // lower lip mid
    return `M ${lx.toFixed(1)} ${cyl.toFixed(1)} Q ${MX} ${upMid.toFixed(1)} ${rx.toFixed(1)} ${cyr.toFixed(1)} ` +
           `Q ${MX} ${loMid.toFixed(1)} ${lx.toFixed(1)} ${cyl.toFixed(1)} Z`;
  }
  function heartPath(cx, cy, s) {
    const p = (x, y) => `${(cx + x * s).toFixed(1)} ${(cy + y * s).toFixed(1)}`;
    return `M ${p(0, 0.35)} C ${p(-0.6, -0.35)} ${p(-1.3, 0.25)} ${p(0, 1.1)} ` +
           `C ${p(1.3, 0.25)} ${p(0.6, -0.35)} ${p(0, 0.35)} Z`;
  }
  function spiralPath(turns, maxR) {
    const steps = turns * 40; let d = "";
    for (let i = 0; i <= steps; i++) {
      const t = i / steps, ang = t * turns * 2 * Math.PI, r = t * maxR;
      d += (i === 0 ? "M " : "L ") + (Math.cos(ang) * r).toFixed(1) + " " + (Math.sin(ang) * r).toFixed(1) + " ";
    }
    return d;
  }
  function sparkPath(s) {
    const p = (x, y) => `${(x * s).toFixed(1)} ${(y * s).toFixed(1)}`;
    return `M ${p(0, -1)} Q ${p(0.18, -0.18)} ${p(1, 0)} Q ${p(0.18, 0.18)} ${p(0, 1)} ` +
           `Q ${p(-0.18, 0.18)} ${p(-1, 0)} Q ${p(-0.18, -0.18)} ${p(0, -1)} Z`;
  }

  // ---------------------------------------------------------------------------
  //  Apply a pose: retarget every spring + set the springiness profile.
  // ---------------------------------------------------------------------------
  let current = "neutral";
  let poseGazeX = 0, poseGazeY = 0, poseSaccade = 1;
  let breathRate = 1.6, breathAmp = 0.012;

  function applyPose(name, snap = false) {
    const p = POSES[name];
    if (!p) return;
    current = name;
    const prof = PROFILES[p.profile] || PROFILES.normal;
    for (const k of POSE_SPRINGS) { S[k].profile(prof.k, prof.c); S[k].to(p[k]); }
    poseGazeX = p.gazeX; poseGazeY = p.gazeY; poseSaccade = p.saccade ?? 1;
    breathRate = p.breathRate; breathAmp = p.breathAmp;

    S.blush.to(p.blush || 0);
    S.heartPupil.to(p.heartPupil ? 1 : 0);
    S.spiral.to(p.spiral ? 1 : 0);
    S.fxHearts.to(p.hearts ? 1 : 0);
    S.fxSparkles.to(p.sparkles ? 1 : 0);
    S.fxZzz.to(p.zzz ? 1 : 0);
    S.fxSweat.to(p.sweat ? 1 : 0);
    S.fxTears.to(p.tears ? 1 : 0);
    S.fxThink.to(p.think ? 1 : 0);

    if (snap) { for (const k of POSE_SPRINGS) S[k].snap(); }
    else {
      // a little reactive squash + tuft whip so it pops into the new mood
      S.sx.kick(0.6); S.sy.kick(-0.6); S.tuftSway.kick(10);
      if (p.kick) { S.sy.kick(p.kick * 0.4); S.ty.kick(-p.kick * 3); }
    }
    updatePanel();
  }

  // ---------------------------------------------------------------------------
  //  Idle life — the part that makes it read as ALIVE. Never fully still.
  // ---------------------------------------------------------------------------
  let idleOn = true;
  let blinkTimer = 0, saccadeTimer = 0, twitchTimer = 0;

  function scheduleBlink() { blinkTimer = 2.2 + Math.random() * 3.6; }
  function doBlink() {
    S.blink.to(0);
    setTimeout(() => S.blink.to(1), 75);
    if (Math.random() < 0.18) {                 // occasional double-blink
      setTimeout(() => { S.blink.to(0); setTimeout(() => S.blink.to(1), 75); }, 230);
    }
    scheduleBlink();
  }
  function scheduleSaccade() { saccadeTimer = 0.7 + Math.random() * 2.0; }
  function doSaccade() {
    const big = Math.random() < 0.25;
    const reach = (big ? 42 : 18) * poseSaccade;
    if (Math.random() < 0.18) { S.sacX.to(0); S.sacY.to(0); }   // sometimes recenter
    else { S.sacX.to((Math.random() * 2 - 1) * reach); S.sacY.to((Math.random() * 2 - 1) * reach * 0.7); }
    scheduleSaccade();
  }
  function scheduleTwitch() { twitchTimer = 3 + Math.random() * 5; }
  function doTwitch() {
    (Math.random() < 0.5 ? S.browLY : S.browRY).kick(-30 - Math.random() * 30);
    scheduleTwitch();
  }
  function tickIdle(dt) {
    if (!idleOn) return;
    blinkTimer -= dt; if (blinkTimer <= 0) doBlink();
    saccadeTimer -= dt; if (saccadeTimer <= 0) doSaccade();
    twitchTimer -= dt; if (twitchTimer <= 0) doTwitch();
  }

  // gentle "look toward the cursor" bias (desktop nicety; decays away)
  let lookBiasX = 0, lookBiasY = 0, lookBiasUntil = 0;

  // ---------------------------------------------------------------------------
  //  SVG refs
  // ---------------------------------------------------------------------------
  const el = {
    face: $("face"), tufts: $("tufts"),
    browL: $("browL"), browR: $("browR"),
    gazeL: $("gazeL"), gazeR: $("gazeR"),
    pupilL: $("pupilL"), pupilR: $("pupilR"),
    heartL: $("heartL"), heartR: $("heartR"), spiralL: $("spiralL"), spiralR: $("spiralR"),
    lidUpL: $("lidUpL"), lidUpR: $("lidUpR"), lidLoL: $("lidLoL"), lidLoR: $("lidLoR"),
    cheekL: $("cheekL"), cheekR: $("cheekR"),
    mouth: $("mouth"), mouthClip: $("mouthClipPath"), teeth: $("teeth"), tongue: $("tongue"),
    fxSweat: $("fxSweat"), fxTears: $("fxTears"), fxThink: $("fxThink"),
    fxZzz: $("fxZzz"), fxHearts: $("fxHearts"), fxSparkles: $("fxSparkles"),
  };
  const glintsL = el.gazeL.querySelectorAll(".glint, .glint2");
  const glintsR = el.gazeR.querySelectorAll(".glint, .glint2");
  const heartKids = el.fxHearts.querySelectorAll(".floatheart");
  const sparkKids = el.fxSparkles.querySelectorAll(".spark");
  const zzzKids = el.fxZzz.querySelectorAll(".zzz");
  const tdotKids = el.fxThink.querySelectorAll(".tdot");
  const tearKids = el.fxTears.querySelectorAll(".tear");

  // one-time path setup for the FX bits
  const HEART_BASES = [{ x: 250, y: 300 }, { x: 500, y: 150 }, { x: 760, y: 320 }];
  const SPARK_BASES = [{ x: 215, y: 300 }, { x: 785, y: 300 }, { x: 300, y: 165 }, { x: 700, y: 165 }, { x: 500, y: 130 }];
  el.heartL.setAttribute("d", heartPath(0, 0, 46));
  el.heartR.setAttribute("d", heartPath(0, 0, 46));
  el.spiralL.setAttribute("d", spiralPath(3, 120));
  el.spiralR.setAttribute("d", spiralPath(3, 120));
  heartKids.forEach((h) => h.setAttribute("d", heartPath(0, 0, 26)));
  sparkKids.forEach((s) => s.setAttribute("d", sparkPath(26)));

  // ---------------------------------------------------------------------------
  //  Render — compose spring values into transforms every frame.
  // ---------------------------------------------------------------------------
  let breathPhase = 0;

  function clampGaze(x, y) {
    const m = Math.hypot(x, y);
    if (m <= GAZE_LIMIT) return [x, y];
    const s = GAZE_LIMIT / m; return [x * s, y * s];
  }

  function render(t, dt) {
    breathPhase += dt * breathRate;
    const breath = Math.sin(breathPhase) * breathAmp;

    // ---- global face transform: tilt + squash/stretch + breathing + micro life
    let tilt = S.tilt.value + Math.sin(t * 0.5) * 0.8 + Math.sin(t * 0.23) * 0.5;
    let ty = S.ty.value + Math.sin(t * 0.7) * 2;
    if (current === "dizzy") { tilt += Math.sin(t * 6) * 6 + Math.sin(t * 3.3) * 4; ty += Math.sin(t * 5) * 6; }
    const sx = S.sx.value * (1 + breath * 0.5);
    const sy = S.sy.value * (1 + breath);
    el.face.setAttribute("transform",
      `translate(${CX} ${CY}) translate(0 ${ty.toFixed(2)}) rotate(${tilt.toFixed(2)}) ` +
      `scale(${sx.toFixed(4)} ${sy.toFixed(4)}) translate(${-CX} ${-CY})`);

    // ---- tufts lag behind the head -> whippy
    S.tuftSway.to(-S.tilt.value * 0.7 + Math.sin(t * 0.6) * 3);
    el.tufts.setAttribute("transform", `rotate(${S.tuftSway.value.toFixed(2)} 500 238)`);

    // ---- brows
    el.browL.setAttribute("transform",
      `translate(${EYE_L.x} ${300 + S.browLY.value.toFixed(2)}) rotate(${S.browLRot.value.toFixed(2)})`);
    el.browR.setAttribute("transform",
      `translate(${EYE_R.x} ${300 + S.browRY.value.toFixed(2)}) rotate(${S.browRRot.value.toFixed(2)})`);

    // ---- gaze (both eyes look the same way): pose + saccade + cursor bias + drift
    if (t > lookBiasUntil) { lookBiasX *= 0.94; lookBiasY *= 0.94; }
    S.gazeX.to(poseGazeX + S.sacX.value + lookBiasX + Math.sin(t * 0.7) * 3);
    S.gazeY.to(poseGazeY + S.sacY.value + lookBiasY + Math.cos(t * 0.6) * 2);
    const [gx, gy] = clampGaze(S.gazeX.value, S.gazeY.value);
    const ps = S.pupilScale.value;
    el.gazeL.setAttribute("transform", `translate(${(EYE_L.x + gx).toFixed(1)} ${(EYE_L.y + gy).toFixed(1)}) scale(${ps.toFixed(3)})`);
    el.gazeR.setAttribute("transform", `translate(${(EYE_R.x + gx).toFixed(1)} ${(EYE_R.y + gy).toFixed(1)}) scale(${ps.toFixed(3)})`);

    // ---- eyelids: openness = min(emotion baseline, blink); + emotional slant
    const open = Math.max(0, Math.min(S.eyeOpen.value, S.blink.value));
    const tyUp = -5 + (1 - open) * 315;
    el.lidUpL.setAttribute("transform", `translate(0 ${tyUp.toFixed(1)}) rotate(${S.lidAngle.value.toFixed(2)} ${EYE_L.x} ${EYE_L.y})`);
    el.lidUpR.setAttribute("transform", `translate(0 ${tyUp.toFixed(1)}) rotate(${(-S.lidAngle.value).toFixed(2)} ${EYE_R.x} ${EYE_R.y})`);
    const loUp = -S.lowerLid.value * 200;
    el.lidLoL.setAttribute("transform", `translate(0 ${loUp.toFixed(1)}) rotate(${(-S.lidAngle.value * 0.25).toFixed(2)} ${EYE_L.x} ${EYE_L.y})`);
    el.lidLoR.setAttribute("transform", `translate(0 ${loUp.toFixed(1)}) rotate(${(S.lidAngle.value * 0.25).toFixed(2)} ${EYE_R.x} ${EYE_R.y})`);

    // ---- heart pupils / spiral eyes fade the normal pupil out
    const heartAmt = clamp01(S.heartPupil.value), spiralAmt = clamp01(S.spiral.value);
    const pupilOp = (1 - Math.max(heartAmt, spiralAmt)).toFixed(3);
    el.pupilL.setAttribute("opacity", pupilOp); el.pupilR.setAttribute("opacity", pupilOp);
    glintsL.forEach((g) => g.setAttribute("opacity", pupilOp));
    glintsR.forEach((g) => g.setAttribute("opacity", pupilOp));
    el.heartL.setAttribute("opacity", heartAmt.toFixed(3));
    el.heartR.setAttribute("opacity", heartAmt.toFixed(3));
    const spin = (t * 220).toFixed(1);
    el.spiralL.setAttribute("opacity", spiralAmt.toFixed(3));
    el.spiralR.setAttribute("opacity", spiralAmt.toFixed(3));
    el.spiralL.setAttribute("transform", `rotate(${spin})`);
    el.spiralR.setAttribute("transform", `rotate(${spin})`);

    // ---- mouth
    const d = mouthPath(S.mW.value, S.mOpen.value, S.mCurve.value, S.mAsym.value);
    el.mouth.setAttribute("d", d);
    el.mouthClip.setAttribute("d", d);
    const mo = S.mOpen.value, mc = S.mCurve.value;
    el.teeth.setAttribute("opacity", (clamp01((mo - 30) / 50) * clamp01((mc + 10) / 30)).toFixed(3));
    el.tongue.setAttribute("opacity", clamp01((mo - 40) / 50).toFixed(3));

    // ---- cheeks
    const blush = clamp01(S.blush.value).toFixed(3);
    el.cheekL.setAttribute("opacity", blush);
    el.cheekR.setAttribute("opacity", blush);

    // ---- floating FX
    updateFX(t);
  }

  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }

  function updateFX(t) {
    setFx(el.fxHearts, S.fxHearts.value, () => {
      heartKids.forEach((h, i) => {
        const ph = (t * 0.5 + i * 0.4) % 1;
        h.setAttribute("transform", `translate(${HEART_BASES[i].x} ${HEART_BASES[i].y - ph * 150}) scale(${1 + ph * 0.4})`);
        h.setAttribute("opacity", Math.sin(ph * Math.PI).toFixed(3));
      });
    });
    setFx(el.fxSparkles, S.fxSparkles.value, () => {
      sparkKids.forEach((s, i) => {
        const ph = (t * 1.6 + i * 0.37) % 1, pulse = Math.max(0, Math.sin(ph * Math.PI));
        s.setAttribute("transform", `translate(${SPARK_BASES[i].x} ${SPARK_BASES[i].y}) scale(${(0.3 + pulse).toFixed(3)}) rotate(${(ph * 90).toFixed(1)})`);
        s.setAttribute("opacity", pulse.toFixed(3));
      });
    });
    setFx(el.fxZzz, S.fxZzz.value, () => {
      zzzKids.forEach((z, i) => {
        const ph = (t * 0.5 + i * 0.33) % 1;
        z.setAttribute("transform", `translate(0 ${(-ph * 70).toFixed(1)})`);
        z.setAttribute("opacity", Math.sin(ph * Math.PI).toFixed(3));
      });
    });
    setFx(el.fxThink, S.fxThink.value, () => {
      tdotKids.forEach((dd, i) => dd.setAttribute("opacity", (0.25 + 0.75 * (0.5 + 0.5 * Math.sin(t * 4 - i * 1.2))).toFixed(3)));
    });
    setFx(el.fxSweat, S.fxSweat.value, () => {
      el.fxSweat.querySelector("path").setAttribute("transform", `translate(0 ${(Math.sin(t * 3) * 4).toFixed(1)})`);
    });
    setFx(el.fxTears, S.fxTears.value, () => {
      tearKids.forEach((tr, i) => tr.setAttribute("transform", `translate(0 ${(Math.sin(t * 1.5 - i * 1.5) * 5 + 5).toFixed(1)})`));
    });
  }
  function setFx(group, amt, animate) {
    const a = clamp01(amt);
    group.setAttribute("opacity", a.toFixed(3));
    if (a > 0.02) animate();
  }

  // ---------------------------------------------------------------------------
  //  Main loop — fixed-step spring integration + render.
  // ---------------------------------------------------------------------------
  const H = 1 / 120;
  let acc = 0, last = performance.now();
  const allSprings = Object.values(S);

  function frame(now) {
    let dt = (now - last) / 1000; last = now;
    if (dt > 0.1) dt = 0.1;                 // don't spiral after a tab pause
    acc += dt;
    while (acc >= H) { for (const sp of allSprings) sp.step(H); acc -= H; }
    tickIdle(dt);
    render(now / 1000, dt);
    requestAnimationFrame(frame);
  }

  // ---------------------------------------------------------------------------
  //  Poke — a reactive squish (click / tap the face).
  // ---------------------------------------------------------------------------
  function poke() {
    S.sx.kick(3); S.sy.kick(-3); S.ty.kick(-34); S.tuftSway.kick(22);
    S.blink.to(0); setTimeout(() => S.blink.to(1.05), 70);
    S.browLY.kick(-40); S.browRY.kick(-40);
  }

  // ---------------------------------------------------------------------------
  //  Debug panel + keyboard
  // ---------------------------------------------------------------------------
  const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="];
  let cycleTimer = null;

  function setEmotion(name) { if (POSES[name]) applyPose(name); }

  function updatePanel() {
    document.querySelectorAll("#emoGrid button").forEach((b) =>
      b.classList.toggle("active", b.dataset.emo === current));
    const cur = $("curEmo"), prof = $("curProfile");
    if (cur) cur.textContent = current;
    if (prof) prof.textContent = (POSES[current].profile) + " spring";
  }

  function buildPanel() {
    const grid = $("emoGrid");
    EMO_ORDER.forEach((emo, i) => {
      const b = document.createElement("button");
      b.dataset.emo = emo;
      b.innerHTML = `${emo}<span class="k">${KEYS[i] || ""}</span>`;
      b.addEventListener("click", () => setEmotion(emo));
      grid.appendChild(b);
    });
    $("panelToggle").addEventListener("click", togglePanel);
    document.querySelectorAll("#controls button").forEach((b) =>
      b.addEventListener("click", () => controlAction(b.dataset.act, b)));
    updatePanel();
  }

  function controlAction(act, btn) {
    if (act === "cycle") {
      if (cycleTimer) { clearInterval(cycleTimer); cycleTimer = null; btn.classList.remove("on"); btn.textContent = "▶ auto-cycle"; }
      else {
        let i = EMO_ORDER.indexOf(current);
        cycleTimer = setInterval(() => { i = (i + 1) % EMO_ORDER.length; setEmotion(EMO_ORDER[i]); }, 2600);
        btn.classList.add("on"); btn.textContent = "■ auto-cycle";
      }
    } else if (act === "idle") {
      idleOn = !idleOn; btn.classList.toggle("on", idleOn); btn.textContent = "idle: " + (idleOn ? "on" : "off");
    } else if (act === "poke") { poke(); }
    else if (act === "fullscreen") { toggleFullscreen(); }
  }

  function togglePanel() { $("panel").classList.toggle("hidden"); }
  function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  }

  window.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    const idx = KEYS.indexOf(e.key);
    if (idx >= 0 && EMO_ORDER[idx]) { setEmotion(EMO_ORDER[idx]); return; }
    if (k === " " || k === "spacebar") { e.preventDefault(); const i = (EMO_ORDER.indexOf(current) + 1) % EMO_ORDER.length; setEmotion(EMO_ORDER[i]); }
    else if (k === "backspace") { setEmotion("neutral"); }
    else if (k === "`" || k === "d") togglePanel();
    else if (k === "i") { idleOn = !idleOn; document.querySelector('[data-act="idle"]').textContent = "idle: " + (idleOn ? "on" : "off"); }
    else if (k === "a") document.querySelector('[data-act="cycle"]').click();
    else if (k === "p") poke();
    else if (k === "f") toggleFullscreen();
  });

  // cursor-follow + poke on the face
  const svg = $("svg");
  svg.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const nx = (e.clientX - r.left) / r.width - 0.5;
    const ny = (e.clientY - r.top) / r.height - 0.5;
    lookBiasX = nx * 70; lookBiasY = ny * 50; lookBiasUntil = performance.now() / 1000 + 1.4;
  });
  svg.addEventListener("pointerdown", poke);

  // ---------------------------------------------------------------------------
  //  WebSocket — the nerve the brain/senses will push emotions down later.
  // ---------------------------------------------------------------------------
  function connectWS() {
    let ws;
    try { ws = new WebSocket(`ws://${location.host}/ws`); }
    catch { setDot(false); return; }
    ws.onopen = () => setDot(true);
    ws.onclose = () => { setDot(false); setTimeout(connectWS, 1500); };
    ws.onerror = () => setDot(false);
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.type === "emotion" && POSES[m.emotion]) applyPose(m.emotion);
      if (m.type === "hello" && m.name) setName(m.name);
    };
  }
  function setDot(ok) { const d = $("dot"); if (d) d.classList.toggle("off", !ok); }
  function setName(name) { $("creatureName").textContent = name; document.title = name; }

  async function loadMeta() {
    try {
      const r = await fetch("/api/emotions");
      const j = await r.json();
      if (j.name) setName(j.name);
    } catch { /* opened without the server; that's fine, face still works */ }
  }

  // ---------------------------------------------------------------------------
  //  Boot
  // ---------------------------------------------------------------------------
  buildPanel();
  applyPose("neutral", true);    // snap, no fly-in
  scheduleBlink(); scheduleSaccade(); scheduleTwitch();
  loadMeta();
  connectWS();
  requestAnimationFrame(frame);
})();
