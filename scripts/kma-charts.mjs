// 기상청 분석일기도(지상·850·700·500·300hPa) 최신본을 받아 site/charts/에 저장한다.
// 지상: 기상청 API허브 WthrChartInfoService/getSurfaceChart(KMA_KEY)로 목록을 받고,
//       실패하면 3시간 간격으로 거슬러 올라가며 직접 찾는다.
// 고층: 00·12Z 이미지를 직접 찾는다.
// 출력: site/charts/*.png, site/charts.json
import { writeFile, mkdir } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const KEY = process.env.KMA_KEY || "";
const IMG = "http://www.kma.go.kr/repositary/image/cht/img";
const API = "https://apihub.kma.go.kr/api/typ02/openApi/WthrChartInfoService";
const UA = { "User-Agent": "study-dashboard" };

const CHARTS = [
  { id: "sfc", name: "지상", prefix: "sfc3", step: 3 },
  { id: "up85", name: "850hPa", prefix: "up85", step: 12 },
  { id: "up70", name: "700hPa", prefix: "up70", step: 12 },
  { id: "up50", name: "500hPa", prefix: "up50", step: 12 },
  { id: "up30", name: "300hPa", prefix: "up30", step: 12 },
];

const p2 = (n) => String(n).padStart(2, "0");
const stamp = (d) => `${d.getUTCFullYear()}${p2(d.getUTCMonth() + 1)}${p2(d.getUTCDate())}${p2(d.getUTCHours())}`;
const fromStamp = (s) => new Date(Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8), +s.slice(8, 10)));

async function retry(fn, n = 3) {
  let err;
  for (let i = 0; i < n; i++) {
    try { return await fn(); } catch (e) { err = e; await new Promise((r) => setTimeout(r, 1500 * (i + 1))); }
  }
  throw err;
}

// 없는 시각도 200 + HTML을 주므로 content-type으로 판정
async function png(url) {
  return retry(async () => {
    const r = await fetch(url, { headers: UA });
    if (!r.ok || !(r.headers.get("content-type") || "").includes("image")) return null;
    return Buffer.from(await r.arrayBuffer());
  });
}

async function surfaceList() {
  if (!KEY) return [];
  const out = [];
  const now = new Date();
  for (const back of [0, 1]) {
    const d = new Date(now.getTime() - back * 864e5);
    const day = stamp(d).slice(0, 8);
    try {
      const j = await retry(async () => {
        const r = await fetch(`${API}/getSurfaceChart?pageNo=1&numOfRows=10&dataType=JSON&code=3&time=${day}&authKey=${KEY}`, { headers: UA });
        return r.json();
      });
      const files = j?.response?.body?.items?.item?.[0]?.["man-file"] || "";
      out.push(...files.replace(/[\[\]]/g, "").split(",").map((s) => s.trim()).filter(Boolean));
    } catch (e) {
      console.error("지상일기도 API 실패:", e.message);
    }
  }
  return [...new Set(out)].sort().reverse();
}

const now = new Date();
const result = { updated: now.toISOString(), charts: [] };
await mkdir(new URL("site/charts/", root), { recursive: true });

for (const c of CHARTS) {
  const cands = [];
  if (c.id === "sfc") {
    for (const u of await surfaceList()) {
      const m = /sfc3_(\d{10})\.png/.exec(u);
      if (m) cands.push({ t: m[1], url: u });
    }
  }
  const base = new Date(now);
  base.setUTCMinutes(0, 0, 0);
  base.setUTCHours(base.getUTCHours() - (base.getUTCHours() % c.step));
  for (let i = 0; i < 8; i++) {
    const t = stamp(new Date(base.getTime() - i * c.step * 3600e3));
    if (!cands.some((x) => x.t === t)) cands.push({ t, url: `${IMG}/${c.prefix}_${t}.png` });
  }
  cands.sort((a, b) => b.t.localeCompare(a.t));
  let got = null;
  for (const x of cands) {
    if (fromStamp(x.t) > now) continue;
    try {
      const buf = await png(x.url);
      if (buf) { got = { ...x, buf }; break; }
    } catch (e) {
      console.error(c.id, x.t, e.message);
    }
  }
  if (!got) { console.error(`${c.name}: 최신 일기도 없음`); continue; }
  await writeFile(new URL(`site/charts/${c.id}.png`, root), got.buf);
  const utc = fromStamp(got.t);
  const kst = new Date(utc.getTime() + 9 * 3600e3);
  result.charts.push({
    id: c.id, name: c.name, file: `charts/${c.id}.png`, utc: utc.toISOString(),
    label: `${kst.getUTCMonth() + 1}/${kst.getUTCDate()} ${p2(kst.getUTCHours())}시 KST (${p2(utc.getUTCHours())}Z)`,
  });
  console.log(`${c.name}: ${got.t}Z`);
}

await writeFile(new URL("site/charts.json", root), JSON.stringify(result, null, 1));
console.log(`일기도 ${result.charts.length}/${CHARTS.length}장`);
