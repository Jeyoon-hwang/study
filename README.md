# 통합 대시보드

노션 DB(프로젝트·기록·마일스톤)를 매시간 읽어 GitHub Pages에 게시하는 정적 사이트.

- `site/` — 페이지 (`index.html`, `data.json`)
- `scripts/fetch-notion.mjs` — 노션 API → `site/data.json`
- `.github/workflows/deploy.yml` — 매시간 갱신·배포

필요한 것: 저장소 Secret `NOTION_TOKEN` (노션 내부 통합 토큰, 3개 DB에 연결 필요).

## 자동 기록
- 섀도 TAF 목표: 심층 분석 500개 (기록 DB「심층」 체크분만 집계, 2027-02-28 점검 60개)
- 체크 시트: `sheets/make_sheets.py` → `site/sheets.pdf` (S1 공부, W1 기상 훈련)
- 시트·사진·녹음을 구글 드라이브 「기록함」에 올리면 매일 22:50 Claude 예약 작업이 판독해 노션 「기록」에 입력
- `scripts/verify-wx.mjs`: METAR/TAF 기록을 aviationweather.gov 실제 METAR와 비교해 채점 → `data/verify.json`
