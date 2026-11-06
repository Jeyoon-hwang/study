// Notion 3개 DB(프로젝트·기록·마일스톤)를 읽어 site/data.json으로 저장한다.
// 사용: NOTION_TOKEN=secret_xxx node scripts/fetch-notion.mjs
import { writeFile } from "node:fs/promises";

const TOKEN = process.env.NOTION_TOKEN;
if (!TOKEN) {
  console.error("NOTION_TOKEN이 없습니다. 기존 data.json을 그대로 둡니다.");
  process.exit(0);
}

const SOURCES = {
  projects: "1858a820-725a-4ad2-99b8-7bd1039cffc0",
  logs: "90c47bdf-4968-4d83-a813-9c60f594a99f",
  milestones: "fd5789f0-25bd-4352-bcd3-9979708abecb",
};

async function queryAll(id) {
  const rows = [];
  let cursor;
  do {
    const res = await fetch(`https://api.notion.com/v1/data_sources/${id}/query`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ page_size: 100, ...(cursor ? { start_cursor: cursor } : {}) }),
    });
    if (!res.ok) throw new Error(`Notion ${id}: ${res.status} ${await res.text()}`);
    const j = await res.json();
    rows.push(...j.results);
    cursor = j.has_more ? j.next_cursor : undefined;
  } while (cursor);
  return rows;
}

const text = (a) => (a || []).map((t) => t.plain_text).join("") || null;
function val(p) {
  if (!p) return null;
  switch (p.type) {
    case "title": return text(p.title);
    case "rich_text": return text(p.rich_text);
    case "number": return p.number;
    case "select": return p.select?.name ?? null;
    case "status": return p.status?.name ?? null;
    case "date": return p.date?.start ?? null;
    case "checkbox": return p.checkbox;
    case "relation": return p.relation.map((r) => r.id);
    case "files": return p.files.map((f) => f.file?.url || f.external?.url).filter(Boolean);
    case "formula": return p.formula[p.formula.type] ?? null;
    case "rollup": return p.rollup.type === "number" ? p.rollup.number : null;
    default: return null;
  }
}
const pick = (page, map) =>
  Object.fromEntries(Object.entries(map).map(([k, name]) => [k, val(page.properties[name])]));

const [p, l, m] = await Promise.all(Object.values(SOURCES).map(queryAll));

const data = {
  updated: new Date().toISOString(),
  projects: p.map((x) => ({
    id: x.id,
    url: x.url,
    ...pick(x, {
      name: "이름", area: "영역", measure: "측정", status: "상태", priority: "우선순위",
      target: "목표", unit: "단위", due: "마감", next: "다음 할 일", memo: "메모",
    }),
  })),
  logs: l.map((x) => ({
    id: x.id,
    ...pick(x, {
      title: "한 일", date: "날짜", projects: "프로젝트", minutes: "시간(분)", qty: "수량",
      score: "점수", memo: "메모", wx: "기상 종류", station: "지점", hit: "적중",
      cause: "틀린 원인", cloud: "구름 종류", mine: "내 값", official: "공식 값",
      solved: "문제 수", correct: "맞은 수", start: "시작", end: "끝", check: "판독 확인 필요",
    }),
  })),
  milestones: m.map((x) => ({
    id: x.id,
    ...pick(x, {
      name: "마일스톤", date: "날짜", criteria: "통과 기준", done: "완료", result: "결과",
      projects: "프로젝트",
    }),
  })),
};

await writeFile(new URL("../site/data.json", import.meta.url), JSON.stringify(data, null, 1));
console.log(`프로젝트 ${data.projects.length} · 기록 ${data.logs.length} · 마일스톤 ${data.milestones.length}`);
