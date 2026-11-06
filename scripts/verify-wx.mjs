// 섀도 TAF·직접 관측 METAR 기록을 실제 METAR(aviationweather.gov)와 비교해 채점한다.
// 입력: site/data.json (logs[].mine = 시트 판독 JSON), 캐시: data/verify.json
// 출력: data/verify.json 갱신 + site/verify.json 복사
import { readFile, writeFile, mkdir } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const data = JSON.parse(await readFile(new URL("site/data.json", root), "utf8"));
let cache = {};
try { cache = JSON.parse(await readFile(new URL("data/verify.json", root), "utf8")); } catch {}

const VIS = ["<1", "1-2", "2-5", "5-8", "8-10", "10+"];
const BASE = ["<500", "500-1k", "1k-3k", "3k-5k", "5k+"];
const WS = ["0-2", "3-6", "7-10", "11-15", "16-20", "21+"];
const visBin = (km) => VIS[km < 1 ? 0 : km < 2 ? 1 : km < 5 ? 2 : km < 8 ? 3 : km < 10 ? 4 : 5];
const baseBin = (ft) => ft == null ? null : BASE[ft < 500 ? 0 : ft < 1000 ? 1 : ft < 3000 ? 2 : ft < 5000 ? 3 : 4];
const wsBin = (kt) => WS[kt <= 2 ? 0 : kt <= 6 ? 1 : kt <= 10 ? 2 : kt <= 15 ? 3 : kt <= 20 ? 4 : 5];
const wdBin = (o) => {
  if ((o.wspd ?? 0) <= 2) return "무풍";
  if (o.wdir === "VRB") return "변동";
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(((+o.wdir % 360) / 45)) % 8];
};
// 한국 METAR는 시정을 m로 보고 → rawOb에서 직접 읽고, 없으면 SM 환산
function visKm(o) {
  const m = / (\d{4})(?:[NSEW]{0,2}|NDV)? /.exec(" " + o.rawOb.replace(/^\S+ \S+ \S+ /, "") + " ");
  if (/CAVOK/.test(o.rawOb)) return 10;
  if (m) return +m[1] >= 9999 ? 10 : +m[1] / 1000;
  if (o.visib === "10+") return 16;
  return o.visib != null ? +o.visib * 1.609 : null;
}
const lowest = (o) => (o.clouds || []).filter((c) => !["CLR", "CAVOK", "SKC", "NSC"].includes(c.cover)).sort((a, b) => a.base - b.base)[0];
const ceiling = (o) => {
  const c = (o.clouds || []).filter((c) => ["BKN", "OVC", "OVX"].includes(c.cover)).sort((a, b) => a.base - b.base)[0];
  return o.vertVis ?? c?.base ?? null;
};
const has = (o, code) => {
  const w = o.wxString || "";
  if (code === "SHRA") return /SHRA/.test(w);
  if (code === "TS") return /TS/.test(w);
  return new RegExp(`(^|[^A-Z])[-+]?(VC)?(\\w*)${code}`).test(w);
};
const binDiff = (arr, a, b) => (a && b ? Math.abs(arr.indexOf(a) - arr.indexOf(b)) : null);

async function metars(stn, endISO, hours) {
  const d = new Date(endISO);
  const p = (n) => String(n).padStart(2, "0");
  const date = `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}_${p(d.getUTCHours())}${p(d.getUTCMinutes())}`;
  const url = `https://aviationweather.gov/api/data/metar?ids=${stn}&format=json&hours=${hours}&date=${date}`;
  const r = await fetch(url, { headers: { "User-Agent": "study-dashboard" } });
  if (r.status === 204) return [];
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return (await r.json()).filter((o) => o.metarType !== "SPECI" || true);
}

const now = Date.now();
let changed = 0;
for (const l of data.logs || []) {
  if (cache[l.id] || !l.mine || !["METAR", "TAF"].includes(l.wx)) continue;
  let mine;
  try { mine = JSON.parse(l.mine); } catch { continue; }
  const stn = (mine.stn || "RKPS").slice(0, 4).toUpperCase();
  try {
    if (l.wx === "METAR" && mine.time) {
      const t = Date.parse(mine.time);
      if (now - t < 3600e3) continue;
      const obs = await metars(stn, new Date(t + 2 * 3600e3).toISOString(), 4);
      const o = obs.sort((a, b) => Math.abs(a.obsTime * 1000 - t) - Math.abs(b.obsTime * 1000 - t))[0];
      if (!o || Math.abs(o.obsTime * 1000 - t) > 45 * 60e3) { cache[l.id] = { status: "no-obs", at: new Date().toISOString() }; changed++; continue; }
      const low = lowest(o);
      const off = {
        wd: wdBin(o), ws: wsBin(o.wspd ?? 0), vis: visBin(visKm(o)),
        cld: low ? (low.cover === "OVX" ? "OVC" : low.cover) : "NSC", base: low ? baseBin(low.base) : null, temp: o.temp,
      };
      const items = {
        풍향: mine.wd === off.wd, 풍속: mine.ws === off.ws, 시정: mine.vis === off.vis,
        운량: mine.cld === off.cld, 운고: off.base == null ? mine.base == null : mine.base === off.base,
        기온: mine.temp != null && Math.abs(mine.temp - off.temp) <= 2,
      };
      const ok = Object.values(items).filter(Boolean).length;
      cache[l.id] = {
        status: "ok", kind: "METAR", raw: o.rawOb, official: off, items,
        score: Math.round((ok / 6) * 100), hit: items.시정 && items.운고,
        tempErr: mine.temp != null ? +(mine.temp - off.temp).toFixed(1) : null,
        visErr: binDiff(VIS, mine.vis, off.vis), at: new Date().toISOString(),
      };
    } else if (l.wx === "TAF" && mine.start) {
      const s = Date.parse(mine.start), e = s + (mine.hours || 12) * 3600e3;
      if (now < e + 3600e3) continue;
      const obs = (await metars(stn, new Date(e).toISOString(), (mine.hours || 12) + 1)).filter((o) => o.obsTime * 1000 >= s && o.obsTime * 1000 <= e);
      if (!obs.length) { cache[l.id] = { status: "no-obs", at: new Date().toISOString() }; changed++; continue; }
      const minVis = Math.min(...obs.map(visKm).filter((v) => v != null));
      const ceils = obs.map(ceiling).filter((v) => v != null);
      const pr = obs.map((o) => o.wxString || "").filter((w) => /RA|SN|DZ/.test(w));
      const off = {
        vis: visBin(minVis), base: ceils.length ? baseBin(Math.min(...ceils)) : "5k+",
        ws: wsBin(Math.max(...obs.map((o) => o.wspd ?? 0))), gust: obs.some((o) => o.wgst),
        precip: !pr.length ? "없음" : pr.some((w) => !w.startsWith("-")) ? "보통+" : "약",
        wx: ["TS", "FG", "BR", "SN", "SHRA"].filter((c) => obs.some((o) => has(o, c))),
      };
      const mw = mine.wx || [];
      const items = {
        시정: mine.vis === off.vis, 운고: mine.base === off.base, 풍속: mine.ws === off.ws,
        돌풍: !!mine.gust === off.gust, 강수: (mine.precip || "없음") === off.precip,
        ...Object.fromEntries(["TS", "FG", "BR", "SN", "SHRA"].map((c) => [c, mw.includes(c) === off.wx.includes(c)])),
      };
      const ok = Object.values(items).filter(Boolean).length;
      cache[l.id] = {
        status: "ok", kind: "TAF", n: obs.length, official: off, items,
        score: Math.round((ok / Object.keys(items).length) * 100),
        hit: items.시정 && items.운고, visErr: binDiff(VIS, mine.vis, off.vis), baseErr: binDiff(BASE, mine.base, off.base),
        at: new Date().toISOString(),
      };
    }
    changed++;
  } catch (err) {
    console.error(l.id, err.message);
  }
}

await mkdir(new URL("data/", root), { recursive: true });
await writeFile(new URL("data/verify.json", root), JSON.stringify(cache, null, 1));
await writeFile(new URL("site/verify.json", root), JSON.stringify(cache));
console.log(`채점 ${changed}건 새로 · 누적 ${Object.keys(cache).length}건`);
