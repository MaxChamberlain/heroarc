
const FILES = __FILES__;
const TYPES = {html:'text/html; charset=utf-8',json:'application/json',svg:'image/svg+xml',js:'text/javascript'};
export default {
  async fetch(req, env) {
    // Second lock: Cloudflare Access must have authenticated this request.
    if (!req.headers.get('Cf-Access-Jwt-Assertion')) return new Response('Forbidden', {status: 403});
    const url = new URL(req.url);
    if (url.pathname === '/api/training') return handleTraining(req, env);
    if (url.pathname === '/api/habits') return handleHabits(req, env);
    if (url.pathname === '/api/habit-config') return handleHabitConfig(req, env);
    if (url.pathname === '/api/goals') return handleGoals(req, env);
    if (url.pathname === '/api/weight') return handleWeight(req, env);
    if (url.pathname === '/api/plan') return handlePlan(req, env);
    if (url.pathname === '/api/data') {
      const d = await env.HEALTH.get('data');
      let out = d || '{}';
      // Overlay edits that are still waiting for the next sync, so a reload right after saving still shows them.
      const jget = async k => { try { return JSON.parse((await env.HEALTH.get(k)) || 'null'); } catch (e) { return null; } };
      try {
        const j = JSON.parse(out);
        const tq = await jget('training_pending');
        if (Array.isArray(tq) && tq.length && j.training) j.training.pending = tq.filter(validTraining).slice(-60);
        const hq = await jget('habit_pending');
        if (Array.isArray(hq) && hq.length && j.habits) j.habits.pending = hq.filter(validHabit).slice(-200);
        const cfg = await jget('habit_cfg_pending');
        if (cfg && validHabitCfg(cfg) && j.habits) j.habits.cfgPending = cfg;
        const gp = await jget('goals_pending');
        if (gp && validGoals(gp)) j.goalsPending = gp;
        const wp = await jget('weight_pending');
        if (Array.isArray(wp) && wp.length) j.weightPending = wp.filter(validWeight).slice(-60);
        const pp = await jget('plan_pending');
        if (pp && validPlan(pp)) j.planPending = pp;
        out = JSON.stringify(j);
      } catch (e) { /* fall back to the plain snapshot */ }
      return new Response(out, {headers: {'content-type':'application/json','cache-control':'no-store'}});
    }
    const key = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
    const f = FILES[key];
    if (!f) return new Response('Not found', {status: 404});
    return new Response(f, {headers: {'content-type': TYPES[key.split('.').pop()] || 'text/plain', 'cache-control':'no-cache', 'x-content-type-options':'nosniff', 'referrer-policy':'no-referrer'}});
  }
};

// POST /api/training : append one training tap to a small queue in KV. Reads nothing back to the caller.
// Called from worker.fetch AFTER the existing Access-header check. Never writes to the sheet; the local sync drains the queue.
const TRAIN_LIMITS = {maxBody: 4096, maxQueue: 300};
function validTraining(ev) {
  if (!ev || typeof ev !== 'object' || Array.isArray(ev)) return false;
  if (typeof ev.id !== 'string' || !/^[A-Za-z0-9_-]{4,40}$/.test(ev.id)) return false;
  if (typeof ev.d !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(ev.d) || isNaN(Date.parse(ev.d + 'T12:00:00Z'))) return false;
  if (!['done', 'partial', 'rest'].includes(ev.s)) return false;
  if (ev.w != null && (typeof ev.w !== 'string' || ev.w.length > 30)) return false;
  const L = ev.lifts == null ? {} : ev.lifts;
  if (typeof L !== 'object' || Array.isArray(L) || Object.keys(L).length > 8) return false;
  for (const [k, v] of Object.entries(L)) {
    if (k.length > 40 || !v || typeof v !== 'object') return false;
    if (v.dir != null && !['up', 'same', 'down'].includes(v.dir)) return false;
    if (v.wt != null && (typeof v.wt !== 'number' || !isFinite(v.wt) || v.wt < 0 || v.wt > 2000)) return false;
    if (v.reps != null && (!Number.isInteger(v.reps) || v.reps < 1 || v.reps > 200)) return false;
  }
  return true;
}
async function handleTraining(req, env) {
  if (req.method !== 'POST') return new Response('Method not allowed', {status: 405});
  // same-origin only: the page sends this custom header; a cross-site form or fetch cannot.
  if (req.headers.get('x-heroarc') !== '1') return new Response('Forbidden', {status: 403});
  const origin = req.headers.get('origin');
  if (origin && origin !== new URL(req.url).origin) return new Response('Forbidden', {status: 403});
  const text = await req.text();
  if (text.length > TRAIN_LIMITS.maxBody) return new Response('Too large', {status: 413});
  let ev; try { ev = JSON.parse(text); } catch (e) { return new Response('Bad JSON', {status: 400}); }
  if (!validTraining(ev)) return new Response('Invalid', {status: 422});
  const rec = {id: ev.id, d: ev.d, w: ev.w || null, s: ev.s, lifts: ev.lifts || {}, t: new Date().toISOString()};
  let q = []; try { q = JSON.parse((await env.HEALTH.get('training_pending')) || '[]'); } catch (e) { q = []; }
  if (!Array.isArray(q)) q = [];
  if (!q.some(x => x && x.id === rec.id)) q.push(rec);
  q = q.slice(-TRAIN_LIMITS.maxQueue);
  await env.HEALTH.put('training_pending', JSON.stringify(q));
  return new Response(JSON.stringify({ok: true}), {headers: {'content-type': 'application/json', 'cache-control': 'no-store'}});
}

// POST /api/habits : append one habit tap (done 1 / undone 0) to a small queue in KV. Same locks as /api/training.
// The local sync drains it into the 'Habit Log' tab; this route never touches the sheet.
const HAB_LIMITS = {maxBody: 1024, maxQueue: 800};
function validHabit(ev) {
  if (!ev || typeof ev !== 'object' || Array.isArray(ev)) return false;
  if (typeof ev.id !== 'string' || !/^[A-Za-z0-9_-]{4,40}$/.test(ev.id)) return false;
  if (typeof ev.d !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(ev.d) || isNaN(Date.parse(ev.d + 'T12:00:00Z'))) return false;
  if (typeof ev.h !== 'string' || !/^[a-z0-9_-]{1,30}$/.test(ev.h)) return false;
  if (ev.v !== 0 && ev.v !== 1) return false;
  return true;
}
async function handleHabits(req, env) {
  if (req.method !== 'POST') return new Response('Method not allowed', {status: 405});
  if (req.headers.get('x-heroarc') !== '1') return new Response('Forbidden', {status: 403});
  const origin = req.headers.get('origin');
  if (origin && origin !== new URL(req.url).origin) return new Response('Forbidden', {status: 403});
  const text = await req.text();
  if (text.length > HAB_LIMITS.maxBody) return new Response('Too large', {status: 413});
  let ev; try { ev = JSON.parse(text); } catch (e) { return new Response('Bad JSON', {status: 400}); }
  if (!validHabit(ev)) return new Response('Invalid', {status: 422});
  const rec = {id: ev.id, d: ev.d, h: ev.h, v: ev.v, t: new Date().toISOString()};
  let q = []; try { q = JSON.parse((await env.HEALTH.get('habit_pending')) || '[]'); } catch (e) { q = []; }
  if (!Array.isArray(q)) q = [];
  if (!q.some(x => x && x.id === rec.id)) q.push(rec);
  q = q.slice(-HAB_LIMITS.maxQueue);
  await env.HEALTH.put('habit_pending', JSON.stringify(q));
  return new Response(JSON.stringify({ok: true}), {headers: {'content-type': 'application/json', 'cache-control': 'no-store'}});
}

// POST /api/habit-config : replace the single pending 'desired Habits tab' (latest edit wins). The local sync writes it to the sheet.
const HC_LIMITS = {maxBody: 4096, maxHabits: 40, maxActive: 8};
function validHabitCfg(ev) {
  if (!ev || typeof ev !== 'object' || Array.isArray(ev)) return false;
  if (typeof ev.id !== 'string' || !/^[A-Za-z0-9_-]{4,40}$/.test(ev.id)) return false;
  const L = ev.list;
  if (!Array.isArray(L) || L.length < 1 || L.length > HC_LIMITS.maxHabits) return false;
  const seen = new Set(); let active = 0;
  for (const x of L) {
    if (!x || typeof x !== 'object' || Array.isArray(x)) return false;
    if (typeof x.n !== 'string') return false;
    const n = x.n.trim();
    if (n.length < 1 || n.length > 30 || /^[=+@\x00-\x1f]/.test(n)) return false;
    if (typeof x.id !== 'string' || !/^[a-z0-9_-]{1,30}$/.test(x.id) || seen.has(x.id)) return false;
    const a = x.a === undefined ? 0 : x.a;
    if (a !== 0 && a !== 1) return false;
    if (!a) active++;
    seen.add(x.id);
  }
  return active <= HC_LIMITS.maxActive;
}
async function handleHabitConfig(req, env) {
  if (req.method !== 'POST') return new Response('Method not allowed', {status: 405});
  if (req.headers.get('x-heroarc') !== '1') return new Response('Forbidden', {status: 403});
  const origin = req.headers.get('origin');
  if (origin && origin !== new URL(req.url).origin) return new Response('Forbidden', {status: 403});
  const text = await req.text();
  if (text.length > HC_LIMITS.maxBody) return new Response('Too large', {status: 413});
  let ev; try { ev = JSON.parse(text); } catch (e) { return new Response('Bad JSON', {status: 400}); }
  if (!validHabitCfg(ev)) return new Response('Invalid', {status: 422});
  const rec = {id: ev.id, list: ev.list.map(x => ({id: x.id, n: x.n.trim(), a: x.a ? 1 : 0})), t: new Date().toISOString()};
  await env.HEALTH.put('habit_cfg_pending', JSON.stringify(rec));
  return new Response(JSON.stringify({ok: true}), {headers: {'content-type': 'application/json', 'cache-control': 'no-store'}});
}

const GOAL_LIMITS = {maxBody: 1024};
const SEX = ['female','male'], ACT = ['sedentary','light','moderate','active','very active'], GOALS = ['lose','maintain','gain'];
function validGoals(ev) {
  if (!ev || typeof ev !== 'object' || Array.isArray(ev)) return false;
  if (typeof ev.id !== 'string' || !/^[A-Za-z0-9_-]{4,40}$/.test(ev.id)) return false;
  if (!SEX.includes(ev.sex) || !ACT.includes(ev.activity) || !GOALS.includes(ev.goal)) return false;
  const num = (v, lo, hi) => typeof v === 'number' && isFinite(v) && v >= lo && v <= hi;
  return num(ev.age, 14, 100) && num(ev.height, 48, 90) && num(ev.weight, 70, 500) && num(ev.kcal, 1000, 6000) && num(ev.protein, 40, 400);
}
async function handleGoals(req, env) {
  if (req.method !== 'POST') return new Response('Method not allowed', {status: 405});
  if (req.headers.get('x-heroarc') !== '1') return new Response('Forbidden', {status: 403});
  const origin = req.headers.get('origin');
  if (origin && origin !== new URL(req.url).origin) return new Response('Forbidden', {status: 403});
  const text = await req.text();
  if (text.length > GOAL_LIMITS.maxBody) return new Response('Too large', {status: 413});
  let ev; try { ev = JSON.parse(text); } catch (e) { return new Response('Bad JSON', {status: 400}); }
  if (!validGoals(ev)) return new Response('Invalid', {status: 422});
  const rec = {id: ev.id, sex: ev.sex, age: ev.age, height: ev.height, weight: ev.weight, activity: ev.activity, goal: ev.goal, kcal: Math.round(ev.kcal), protein: Math.round(ev.protein), t: new Date().toISOString()};
  await env.HEALTH.put('goals_pending', JSON.stringify(rec));
  return new Response('{"ok":true}', {headers: {'content-type': 'application/json', 'cache-control': 'no-store'}});
}

const WT_LIMITS = {maxBody: 512, maxQueue: 200};
function validWeight(ev) {
  if (!ev || typeof ev !== 'object' || Array.isArray(ev)) return false;
  if (typeof ev.id !== 'string' || !/^[A-Za-z0-9_-]{4,40}$/.test(ev.id)) return false;
  if (typeof ev.d !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(ev.d) || isNaN(Date.parse(ev.d + 'T12:00:00Z'))) return false;
  return typeof ev.w === 'number' && isFinite(ev.w) && ev.w >= 70 && ev.w <= 500;
}
async function handleWeight(req, env) {
  if (req.method !== 'POST') return new Response('Method not allowed', {status: 405});
  if (req.headers.get('x-heroarc') !== '1') return new Response('Forbidden', {status: 403});
  const origin = req.headers.get('origin');
  if (origin && origin !== new URL(req.url).origin) return new Response('Forbidden', {status: 403});
  const text = await req.text();
  if (text.length > WT_LIMITS.maxBody) return new Response('Too large', {status: 413});
  let ev; try { ev = JSON.parse(text); } catch (e) { return new Response('Bad JSON', {status: 400}); }
  if (!validWeight(ev)) return new Response('Invalid', {status: 422});
  const rec = {id: ev.id, d: ev.d, w: Math.round(ev.w * 10) / 10, t: new Date().toISOString()};
  let q = []; try { q = JSON.parse((await env.HEALTH.get('weight_pending')) || '[]'); } catch (e) { q = []; }
  if (!Array.isArray(q)) q = [];
  if (!q.some(x => x && x.id === rec.id)) q.push(rec);
  await env.HEALTH.put('weight_pending', JSON.stringify(q.slice(-WT_LIMITS.maxQueue)));
  return new Response('{"ok":true}', {headers: {'content-type': 'application/json', 'cache-control': 'no-store'}});
}

// POST /api/plan : replace the single pending 'desired training plan' (latest edit wins). The local sync writes it to the Plan tab.
const PLAN_LIMITS = {maxBody: 12000, maxWorkouts: 7, maxExercises: 14, maxStars: 8};
function validPlan(ev) {
  if (!ev || typeof ev !== 'object' || Array.isArray(ev)) return false;
  if (typeof ev.id !== 'string' || !/^[A-Za-z0-9_-]{4,40}$/.test(ev.id)) return false;
  const W = ev.workouts;
  if (!Array.isArray(W) || W.length < 1 || W.length > PLAN_LIMITS.maxWorkouts) return false;
  const bad = s => /^[=+@\x00-\x1f]/.test(s) || /[\x00-\x1f]/.test(s);
  const names = new Set();
  for (const w of W) {
    if (!w || typeof w !== 'object' || Array.isArray(w) || typeof w.name !== 'string') return false;
    const n = w.name.trim();
    if (n.length < 1 || n.length > 30 || bad(n) || names.has(n.toLowerCase())) return false;
    names.add(n.toLowerCase());
    const E = w.ex;
    if (!Array.isArray(E) || E.length < 1 || E.length > PLAN_LIMITS.maxExercises) return false;
    const seen = new Set(); let stars = 0;
    for (const x of E) {
      if (!x || typeof x !== 'object' || Array.isArray(x) || typeof x.n !== 'string') return false;
      const xn = x.n.trim(), xs = x.sets == null ? '' : x.sets;
      if (xn.length < 1 || xn.length > 40 || bad(xn) || seen.has(xn.toLowerCase())) return false;
      if (typeof xs !== 'string' || xs.length > 20 || bad(xs)) return false;
      if (x.star !== 0 && x.star !== 1) return false;
      seen.add(xn.toLowerCase()); stars += x.star;
    }
    if (stars > PLAN_LIMITS.maxStars) return false;
  }
  return true;
}
async function handlePlan(req, env) {
  if (req.method !== 'POST') return new Response('Method not allowed', {status: 405});
  if (req.headers.get('x-heroarc') !== '1') return new Response('Forbidden', {status: 403});
  const origin = req.headers.get('origin');
  if (origin && origin !== new URL(req.url).origin) return new Response('Forbidden', {status: 403});
  const text = await req.text();
  if (text.length > PLAN_LIMITS.maxBody) return new Response('Too large', {status: 413});
  let ev; try { ev = JSON.parse(text); } catch (e) { return new Response('Bad JSON', {status: 400}); }
  if (!validPlan(ev)) return new Response('Invalid', {status: 422});
  const rec = {id: ev.id, workouts: ev.workouts.map(w => ({name: w.name.trim(), ex: w.ex.map(x => ({n: x.n.trim(), sets: (x.sets || '').trim(), star: x.star}))})), t: new Date().toISOString()};
  await env.HEALTH.put('plan_pending', JSON.stringify(rec));
  return new Response('{"ok":true}', {headers: {'content-type': 'application/json', 'cache-control': 'no-store'}});
}
