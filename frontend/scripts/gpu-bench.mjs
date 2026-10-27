// GPU render-cost benchmark for the galaxy view, driven over the Chrome DevTools
// Protocol (Node >= 22, no dependencies).
//
//   node scripts/gpu-bench.mjs --url http://127.0.0.1:4173/ [--launch chromium] [--swiftshader]
//                              [--port 9333] [--dpr 2] [--size 1440x900]
//
// --launch starts a fresh headless browser; without it, connect to a browser
// already listening on --port (e.g. a visible Chrome on a test laptop).
// Each variant forces continuous rendering of a static, fully zoomed-out scene
// and reports frame times, so differences are pure render cost.

import { spawn } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, arg, i, all) => {
    if (arg.startsWith('--')) pairs.push([arg.slice(2), all[i + 1]?.startsWith('--') || all[i + 1] === undefined ? true : all[i + 1]])
    return pairs
  }, []),
)
const port = Number(args.port ?? 9333)
const [width, height] = String(args.size ?? '1440x900').split('x').map(Number)
const dpr = Number(args.dpr ?? 2)
const pageUrl = new URL(args.url ?? 'http://127.0.0.1:4173/')
pageUrl.searchParams.set('debug', '1')
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

let browser
let profileDir
if (args.launch) {
  profileDir = mkdtempSync(join(tmpdir(), 'gpu-bench-'))
  const flags = [
    `--remote-debugging-port=${port}`, `--user-data-dir=${profileDir}`, '--headless=new',
    `--window-size=${width},${height}`, '--no-first-run', '--no-default-browser-check',
    ...(args.swiftshader ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : ['--enable-gpu', '--ignore-gpu-blocklist']),
    'about:blank',
  ]
  browser = spawn(args.launch, flags, { stdio: 'ignore' })
}

async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
      const page = targets.find(t => t.type === 'page')
      if (page) return page.webSocketDebuggerUrl
    } catch {}
    await sleep(500)
  }
  throw new Error(`no browser on port ${port}`)
}

const ws = new WebSocket(await connect())
await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }))
let nextId = 0
const pending = new Map()
ws.addEventListener('message', event => {
  const msg = JSON.parse(event.data)
  if (pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id) }
})
const send = (method, params = {}) => new Promise(resolve => {
  pending.set(++nextId, resolve)
  ws.send(JSON.stringify({ id: nextId, method, params }))
})
const evaluate = async expression => {
  const reply = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (reply.result?.exceptionDetails) throw new Error(JSON.stringify(reply.result.exceptionDetails).slice(0, 300))
  return reply.result?.result?.value
}

await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: dpr, mobile: false })
await send('Page.navigate', { url: pageUrl.toString() })
const env = await evaluate(`(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 300 && !(window.__galaxyDebug && (window.__staffGalaxyMetrics || []).some(m => m.name === 'cosmos-ready')); i++) await sleep(100);
  await sleep(1500);
  const gl = document.createElement('canvas').getContext('webgl2');
  const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
  const canvas = document.querySelector('canvas');
  return { renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown', dpr: devicePixelRatio,
           canvas: canvas ? canvas.width + 'x' + canvas.height : null, ready: !!window.__galaxyDebug };
})()`)
console.log('ENV', JSON.stringify(env))

async function measure(label, setup) {
  const stats = await evaluate(`(async () => {
    const dbg = window.__galaxyDebug, cosmos = dbg.cosmos();
    ${setup}
    dbg.wake(30000);
    await new Promise(r => setTimeout(r, 700));
    // At least 3 s and 10 frames (slow software rendering), at most 20 s.
    const frames = []; let last = performance.now(); let on = true;
    const tick = now => { frames.push(now - last); last = now; if (on) requestAnimationFrame(tick) };
    requestAnimationFrame(tick);
    const t0 = performance.now();
    while (performance.now() - t0 < 20000 && (performance.now() - t0 < 3000 || frames.length < 10)) await new Promise(r => setTimeout(r, 100));
    on = false;
    const f = frames.slice(2).sort((a, b) => a - b), sum = f.reduce((a, b) => a + b, 0);
    if (!f.length) return { fps: 0, p50: null, p95: null, frames: frames.length };
    return { fps: +(1000 * f.length / sum).toFixed(1), p50: +f[Math.floor(f.length * .5)].toFixed(1), p95: +f[Math.floor(f.length * .95)].toFixed(1) };
  })()`)
  console.log(`RESULT ${label.padEnd(34)} ${JSON.stringify(stats)}`)
}

// Adaptive quality as shipped: no overrides, let the controller settle while
// the camera keeps the renderer busy, then measure.
const auto = await evaluate(`(async () => {
  const dbg = window.__galaxyDebug, cosmos = dbg.cosmos();
  const t0 = performance.now();
  while (performance.now() - t0 < 25000) {
    cosmos.zoom(0.9 + Math.random() * 0.2, 400, false);
    dbg.wake(2000);
    await new Promise(r => setTimeout(r, 500));
  }
  return dbg.quality();
})()`)
console.log(`       adaptive quality settled at level ${auto}`)
await measure(`adaptive (level ${auto})`, `cosmos.fitView(0, 0.18, false);`)

const reset = `cosmos.setConfigPartial({ pixelRatio: Math.min(devicePixelRatio, 2), renderLinks: true }); dbg.setEdgeBudget(1e9); cosmos.fitView(0, 0.18, false);`
await measure('all edges, DPR 2 (zoomed out)', reset)
await measure('all edges, DPR 1', `${reset} cosmos.setConfigPartial({ pixelRatio: 1 });`)
await measure('50K edges, DPR 2', `${reset} dbg.setEdgeBudget(50000);`)
await measure('20K edges, DPR 2', `${reset} dbg.setEdgeBudget(20000);`)
// Uploading only a prefix of the links (instead of zero widths) — and how long
// that upload stalls the main thread.
for (const n of [50000, 20000]) {
  await measure(`setLinks prefix ${n / 1000}K, DPR 2`, `${reset}
    const p = dbg.payload(); const t = performance.now();
    cosmos.setLinks(p.sortedLinks.subarray(0, ${n} * 2));
    cosmos.setLinkColors(p.sortedLinkColors.subarray(0, ${n} * 4));
    cosmos.setLinkWidths(p.sortedLinkWidths.subarray(0, ${n}));
    cosmos.render();
    window.__uploadMs = performance.now() - t;`)
  console.log(`       upload stall: ${(await evaluate('window.__uploadMs')).toFixed(1)} ms`)
}
await evaluate(`(() => { const dbg = window.__galaxyDebug, cosmos = dbg.cosmos(), p = dbg.payload();
  cosmos.setLinks(p.sortedLinks); cosmos.setLinkColors(p.sortedLinkColors); cosmos.render(); return true })()`)
await measure('no edges (points only), DPR 2', `${reset} cosmos.setConfigPartial({ renderLinks: false });`)
await measure('no edges, DPR 1', `${reset} cosmos.setConfigPartial({ renderLinks: false, pixelRatio: 1 });`)

ws.close()
if (browser) {
  browser.kill()
  await sleep(500)
  rmSync(profileDir, { recursive: true, force: true })
}
