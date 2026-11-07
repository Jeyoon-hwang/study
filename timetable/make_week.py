from pathlib import Path
OUT = Path(__file__).parent
DAYS = ["월","화","수","목","금","토","일"]
CAT = {  # 이름: (배경, 글자)
 "고정": ("#EFEDE6","#444441"), "수업": ("#E2E0D8","#444441"),
 "Stewart": ("#D6E6F8","#0C447C"), "토스": ("#F8DCE6","#72243E"),
 "내신": ("#FAE6C4","#633806"), "기상": ("#D2F0E4","#085041"),
 "체력": ("#F8DDD2","#712B13"), "관악부": ("#E4E1FA","#3C3489"), "휴식": ("#FFFFFF","#5F5E5A"),
}
def t(s): h,m = map(int,s.split(":")); return h*60+m
WEEKDAY_COMMON = [("06:30","07:00","기상·준비","고정"),("07:00","08:00","아침·등교","고정"),
 ("17:00","17:40","복귀·휴식","휴식"),("17:40","18:15","저녁","고정"),("21:00","21:45","청소·점호","고정"),
 ("21:45","22:00","팔굽혀펴기 15×5","체력"),("22:00","22:15","일기도 15분","기상"),("22:45","23:00","사진 → 기록함","고정")]
MONTHU = WEEKDAY_COMMON+[("08:00","17:00","수업","수업"),("18:15","19:00","Stewart 문제","Stewart"),
 ("19:00","21:00","관악부","관악부"),("22:15","22:45","토스 답변 녹음","토스")]
TUEWED = WEEKDAY_COMMON+[("08:00","17:00","수업","수업"),("18:15","19:45","Stewart 개념+문제","Stewart"),
 ("19:45","20:30","토스","토스"),("20:30","21:00","내신 복습·예습","내신"),("22:15","22:45","내신·수행평가","내신")]
FRI = [("06:30","07:00","기상·준비","고정"),("07:00","08:00","아침·등교","고정"),("08:00","14:30","수업","수업"),
 ("14:30","17:00","Stewart 몰아서","Stewart"),("17:00","17:40","휴식","휴식"),("17:40","18:15","저녁","고정"),
 ("18:15","19:15","METAR 관측·섀도 TAF","기상"),("19:15","21:00","내신 주간 정리","내신"),("21:00","21:45","청소·점호","고정"),
 ("21:45","22:00","팔굽혀펴기","체력"),("22:00","23:00","자유","휴식")]
SAT = [("07:30","08:30","기상·아침","고정"),("09:00","12:00","Stewart 새 절","Stewart"),("12:00","13:00","점심","고정"),
 ("13:00","15:00","Stewart 연습문제","Stewart"),("15:00","16:00","일기도 손 분석·Skew-T","기상"),("16:00","17:00","토스 실전","토스"),
 ("17:00","18:00","운동 (3km·윗몸)","체력"),("18:00","19:00","저녁","고정"),("19:00","21:00","내신·수행평가","내신"),
 ("21:00","21:45","청소·점호","고정"),("21:45","23:00","자유","휴식")]
SUN = [("07:30","08:30","기상·아침","고정"),("09:00","11:00","주간 복습 · 빈 종이 테스트","Stewart"),
 ("11:00","11:30","다음 주 계획·시트 뽑기","고정"),("11:30","19:00","쉬는 날","휴식"),
 ("19:00","20:00","월요일 예습","내신"),("20:00","21:00","자유","휴식"),("21:00","21:45","청소·점호","고정"),("21:45","23:00","자유","휴식")]
PLAN = [MONTHU,TUEWED,TUEWED,MONTHU,FRI,SAT,SUN]
T0,T1,SLOT = t("06:30"), t("23:30"), 15
ROWS = (T1-T0)//SLOT
tot = {}
cells = ""
for d,blocks in enumerate(PLAN):
    for s,e,label,c in blocks:
        r0=(t(s)-T0)//SLOT+2; r1=(t(e)-T0)//SLOT+2
        tot[c]=tot.get(c,0)+t(e)-t(s)
        bg,fg = CAT[c]; mins=t(e)-t(s)
        small = ' sm' if mins<=15 else ''
        tm = f'<span class="tm">{s}–{e}</span>' if mins>=45 else ''
        cells += f'<div class="b{small}" style="grid-column:{d+2};grid-row:{r0}/{r1};background:{bg};color:{fg}">{tm}<b>{label}</b></div>'
hours = ""
for i in range(ROWS+1):
    m=T0+i*SLOT
    if m%60==0 and m<T1:
        hours += f'<div class="h" style="grid-row:{i+2}/{i+6}">{m//60}</div>'
lines = "".join(f'<div class="gl" style="grid-row:{i+2}"></div>' for i in range(0,ROWS,4) if (T0+i*SLOT)%60==0)
head = '<div class="dh" style="grid-column:1"></div>'+"".join(f'<div class="dh" style="grid-column:{i+2}">{d}</div>' for i,d in enumerate(DAYS))
fmt = lambda m: f"{m//60}h" + (f" {m%60}m" if m%60 else "")
legend = "".join(f'<span class="lg"><i style="background:{CAT[c][0]}"></i>{n} <b>{fmt(tot.get(c,0))}</b></span>' for c,n in
  [("Stewart","Stewart"),("토스","토스"),("내신","내신"),("기상","기상 훈련"),("체력","체력"),("관악부","관악부")])
html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@page{{size:A4 landscape;margin:0}}*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Noto Sans CJK KR',sans-serif;color:#2C2C2A;-webkit-print-color-adjust:exact}}
.pg{{width:297mm;height:210mm;padding:8mm 9mm 7mm}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:3mm}}
h1{{font-size:16pt;font-weight:800;letter-spacing:-.3pt}} .sub{{font-size:8pt;color:#5F5E5A}}
.lgs{{display:flex;gap:4mm;flex-wrap:wrap;font-size:7.6pt}} .lg i{{display:inline-block;width:3mm;height:3mm;border:.2mm solid #B4B2A9;border-radius:.6mm;margin-right:1mm;vertical-align:-.4mm}}
.g{{display:grid;grid-template-columns:7mm repeat(7,1fr);grid-template-rows:6mm repeat({ROWS},minmax(0,1fr));height:166mm;column-gap:1.2mm;position:relative}}
.dh{{grid-row:1;font-size:10pt;font-weight:800;text-align:center;border-bottom:.4mm solid #2C2C2A}}
.h{{grid-column:1;font-size:7pt;color:#888780;text-align:right;padding-right:1mm;margin-top:-1.6mm}}
.gl{{grid-column:2/9;border-top:.2mm solid #E2E0D8;z-index:0}}
.b{{z-index:1;border-radius:1.2mm;padding:.5mm 1.4mm;font-size:7pt;line-height:1.15;overflow:hidden;border:.2mm solid rgba(0,0,0,.08);display:flex;flex-direction:column;justify-content:center}}
.b b{{font-weight:700}} .b .tm{{font-size:6pt;opacity:.75}} .b.sm{{font-size:6pt;padding:0 1.2mm}}
.foot{{margin-top:2.5mm;display:flex;justify-content:space-between;font-size:7pt;color:#5F5E5A;gap:6mm}}
</style></head><body><div class="pg">
<div class="top"><div><h1>주간 시간표</h1><div class="sub">2학기 · 11월~12/16 (과전 실험 기간) 기준 · 매주 같은 틀</div></div><div class="lgs">{legend}</div></div>
<div class="g">{head}{lines}{hours}{cells}</div>
<div class="foot"><span>과전 촬영 날엔 그 시간 Stewart를 실험실에서 · 월·목은 관악부라 짧게, 금·토에 몰아서</span><span>12/17부터 내신 모드로 바꿈 · 일요일 오후는 무조건 쉼</span><span>매일 22:45 체크 시트 사진 → 드라이브 「기록함」</span></div>
</div></body></html>'''
(OUT/"week.html").write_text(html,encoding="utf-8")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1123,"height":794})
    pg.goto((OUT/"week.html").resolve().as_uri()); pg.wait_for_timeout(400)
    pg.pdf(path=str(OUT/"주간시간표.pdf"),width="297mm",height="210mm",print_background=True)
    pg.screenshot(path="/tmp/claude-0/-home-claude/08608745-79ad-567e-8880-3054ac0b1c7b/scratchpad/week.png")
    b.close()
print({k:v/60 for k,v in tot.items()})
