# 통합 대시보드

노션 DB(프로젝트·기록·마일스톤)를 매시간 읽어 GitHub Pages에 게시하는 정적 사이트.

- `site/` — 페이지 (`index.html`, `data.json`)
- `scripts/fetch-notion.mjs` — 노션 API → `site/data.json`
- `.github/workflows/deploy.yml` — 매시간 갱신·배포

필요한 것: 저장소 Secret `NOTION_TOKEN` (노션 내부 통합 토큰, 3개 DB에 연결 필요).
