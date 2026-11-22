"""칸 칠하기 체크 시트 생성 → HTML → PDF (playwright)."""
from pathlib import Path
OUT = Path(__file__).parent

CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;color:#111;-webkit-print-color-adjust:exact}
.page{width:210mm;height:297mm;padding:11mm 10mm 8mm;position:relative;page-break-after:always}
.reg{position:absolute;width:6mm;height:6mm;background:#000}
.tl{top:4mm;left:4mm}.tr{top:4mm;right:4mm}.bl{bottom:4mm;left:4mm}.br{bottom:4mm;right:4mm}
.head{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:.6mm solid #000;padding-bottom:2mm;margin-bottom:2.5mm}
.title{font-size:15pt;font-weight:800;letter-spacing:-.3pt}
.code{font-size:9pt;font-weight:700;border:.4mm solid #000;padding:.6mm 2mm;border-radius:1mm}
.hint{font-size:7.2pt;color:#444;margin-bottom:2mm}
.blk{border:.35mm solid #000;border-radius:1.5mm;padding:1.6mm 2.2mm;margin-bottom:2.2mm}
.blk h3{font-size:8.5pt;font-weight:800;margin-bottom:1mm;display:flex;justify-content:space-between}
.ln{display:flex;align-items:center;gap:1.2mm;min-height:6.1mm;flex-wrap:nowrap}
.lb{font-size:7.4pt;font-weight:700;width:14mm;flex:none}
.sub{font-size:6.6pt;color:#333;margin:0 .6mm 0 1.6mm;flex:none}
.b{display:inline-flex;flex-direction:column;align-items:center;flex:none}
.b i{display:block;width:4.3mm;height:4.3mm;border:.3mm solid #000;border-radius:50%}
.b span{font-size:5.6pt;line-height:1.05;margin-top:.25mm;white-space:nowrap}
.w i{width:4.3mm}
.sep{width:.3mm;height:5mm;background:#999;margin:0 1.2mm;flex:none}
.foot{position:absolute;bottom:8mm;left:12mm;right:12mm;font-size:6.6pt;color:#555;display:flex;justify-content:space-between}
"""

def bub(labels):
    return "".join(f'<span class="b"><i></i><span>{l}</span></span>' for l in labels)

def line(label, *parts):
    inner = ""
    for p in parts:
        if p == "|":
            inner += '<span class="sep"></span>'
        elif isinstance(p, tuple):
            inner += f'<span class="sub">{p[0]}</span>' + bub(p[1])
        else:
            inner += bub(p)
    return f'<div class="ln"><span class="lb">{label}</span>{inner}</div>'

D10 = [str(i) for i in range(10)]
def date_line():
    return line("날짜", ("월", [str(i) for i in range(1, 13)]), "|", ("일 십", ["0","1","2","3"]), ("일", D10))

def page(title, code, hint, body, foot):
    regs = "".join(f'<div class="reg {c}"></div>' for c in ("tl","tr","bl","br"))
    return f'''<div class="page">{regs}
<div class="head"><div class="title">{title}</div><div class="code">{code}</div></div>
<div class="hint">{hint}</div>{body}
<div class="foot"><span>{foot}</span><span>칠한 뒤 사진 → 드라이브 「기록함」</span></div></div>'''

# ---------- 공부 시트 (S1) ----------
SUBJ = ["대수","Stewart","Boas","Halliday","Ahrens","W&H","Holton","한능검","컴활","토스","강수정","내신","과전","기타"]
HOURS = [str(h) for h in range(6, 25)]
# 평일: 수업 끝나고 18:00~23:00만 자유시간 (월·목은 관악부라 18~19시만)
WEEKDAY_HOURS = [str(h) for h in range(18, 24)]
WEEKEND_HOURS = [str(h) for h in range(7, 25)]
MINS = ["00","10","20","30","40","50"]
def study_block(n, hours=HOURS):
    return f'''<div class="blk"><h3><span>세션 {n}</span><span style="font-weight:500;font-size:6.8pt">안 쓴 세션은 비워두기</span></h3>
{line("과목", SUBJ)}
{line("장·강", ("십", ["0","1","2","3","4"]), ("일", D10), "|", ("이 장 끝", ["완료"]), "|", ("종류", ["개념","예제","연습","Review","기출"]))}
{line("시작", ("시", hours), "|", ("분", MINS))}
{line("끝", ("시", hours), "|", ("분", MINS))}
{line("푼 문제", ("십", D10), "|", ("일", D10))}
{line("맞은 문제", ("십", D10), "|", ("일", D10))}
</div>'''

HINT = "동그라미를 꽉 칠해. 체크·X 표시 말고 칠하기. 잘못 칠하면 크게 X 긋고 옆에 다시 칠해. 시간은 10분 단위로 가까운 쪽."
study = page("공부 체크 시트 · 평일", "S1",
    HINT + " 평일은 18~23시만 (월·목은 관악부라 18~19시). 23시 넘으면 끝을 23시 50분까지.",
    date_line() + '<div style="height:2mm"></div>' + "".join(study_block(i, WEEKDAY_HOURS) for i in range(1, 5)),
    "S1 평일 · 세션 4개") + page("공부 체크 시트 · 주말", "S1",
    HINT + " 주말·방학용 (7~24시).",
    date_line() + '<div style="height:2mm"></div>' + "".join(study_block(i, WEEKEND_HOURS) for i in range(1, 5)),
    "S1 주말 · 세션 4개 · 모자라면 2장")

# ---------- 기상 시트 (W1) ----------
STN = ["RKPS 사천","RKPK 김해","RKPC 제주","RKTU 청주","RKSI 인천","RKSS 김포"]
WD = ["N","NE","E","SE","S","SW","W","NW","무풍","변동"]
WS = ["0-2","3-6","7-10","11-15","16-20","21+"]
VIS = ["<1","1-2","2-5","5-8","8-10","10+"]
WX = ["없음","BR","FG","HZ","DZ","RA","SHRA","SN","TS"]
CLD = ["NSC","FEW","SCT","BKN","OVC"]
BASE = ["<500","500-1k","1k-3k","3k-5k","5k+"]
def metar_block(n):
    return f'''<div class="blk"><h3><span>직접 관측 METAR {n}</span><span style="font-weight:500;font-size:6.8pt">하늘 사진 같이 올리면 좋음</span></h3>
{date_line()}
{line("시각", ("시(KST)", [str(h) for h in range(24)]), "|", ("분", ["00","30"]))}
{line("지점", STN)}
{line("바람", ("풍향", WD), "|", ("풍속 kt", WS))}
{line("시정", ("km", VIS), "|", ("현천(여러 개)", WX))}
{line("구름", ("최저층 운량", CLD), "|", ("운고 ft", BASE))}
{line("기온", ("부호", ["영하"]), ("십", ["0","1","2","3"]), ("일", D10))}
</div>'''
def taf_block():
    return f'''<div class="blk"><h3><span>섀도 TAF</span><span style="font-weight:500;font-size:6.8pt">공식 TAF 보기 전에 칠하기 · 기간 중 가장 나쁜 값</span></h3>
{date_line()}
{line("시작", ("시(KST)", [str(h) for h in range(24)]))}
{line("지점", STN, "|", ("길이", ["6h","12h","24h"]))}
{line("최악 시정", ("km", VIS), "|", ("최저 운고 ft", BASE))}
{line("최대 풍속", ("kt", WS), "|", ("돌풍", ["있음"]), "|", ("강수", ["없음","약","보통+"]))}
{line("현상", ("있을 것", ["TS","FG","BR","SN","SHRA"]))}
</div>'''
wx = page("기상 훈련 시트", "W1",
    "관측은 창밖을 보고 바로. 섀도 TAF는 공식 TAF를 보기 전에. 매일 밤 실제 METAR와 자동 비교해서 적중·오차를 노션에 기록함.",
    metar_block(1) + metar_block(2) + taf_block(), "W1 · METAR 2 + TAF 1")

# ---------- 시험·수행 시트 (E1) ----------
ESUBJ = ["국어A","국어B","국어C","수학","영어A","영어B","영어C","사회A","사회B","과학A","과학B","기상","항공법규","기타"]
def exam_block(n):
    return f'''<div class="blk"><h3><span>기록 {n}</span><span style="font-weight:500;font-size:6.8pt">점수 나온 날 칠하기 · 안 쓴 칸은 비워두기</span></h3>
{date_line()}
{line("과목", ESUBJ)}
{line("종류", ["중간","기말","수행","형성","모의"], "|", ("수행 몇 번째", ["1","2","3","4"]))}
{line("점수", ("백", ["0","1","2","3","4"]), ("십", D10), ("일", D10))}
{line("소수·만점", ("소수", [".0",".2",".4",".5",".6",".8"]), "|", ("만점", ["10","20","30","50","100","200","300","400"]))}
{line("평균", ("알면 십", D10), ("일", D10))}
{line("등수", ("범위", ["통제과","전교","반"]), "|", ("백", ["0","1"]), ("십", D10), ("일", D10))}
</div>'''
exam = page("시험·수행 기록 시트", "E1",
    "점수·등수 받은 날 칠해. 수행은 몇 번째 수행인지(그 과목에서 1, 2…)도. 평균은 알면 칠하기. 노션 마일스톤에 같은 과목 시험·수행이 있으면 자동으로 완료 체크·결과 입력됨.",
    "".join(exam_block(i) for i in range(1, 5)), "E1 · 4건")

# ---------- 섀도 TAF 심층·일기도 채점 시트 (T1) ----------
TSTN = ["RKPS 사천","RKPK 김해","RKPC 제주","RKTU 청주","기타"]
CAUSE = ["타이밍","강도","모델 과신","지형","기단","안정도","변화군 형식","로컬 패턴"]
OX = ["맞음","틀림"]
def deep_block(n):
    return f'''<div class="blk"><h3><span>섀도 TAF 채점 {n}</span><span style="font-weight:500;font-size:6.8pt">유효기간 끝난 뒤 실제 METAR랑 맞춰 보고 칠하기</span></h3>
{date_line()}
{line("TAF", ("지점", TSTN), "|", ("시작 시(KST)", ["0","3","6","9","12","15","18","21"]))}
{line("적중", ("바람", OX), "|", ("시정", OX), "|", ("운고", OX), "|", ("현천", OX))}
{line("틀린 원인", CAUSE)}
{line("열어 본 것", ["일기도","Skew-T","위성","레이더","모델 비교"], "|", ("심층", ["완료"]))}
{line("걸린 시간", ("십분", ["0","1","2","3","4","5","6","7","8","9"]))}
</div>'''
def chart_block():
    G = ["맞음","근접","틀림"]
    return f'''<div class="blk"><h3><span>지상일기도 손 분석 채점</span><span style="font-weight:500;font-size:6.8pt">「정답」 탭(같은 시각 기상청 분석일기도)과 비교</span></h3>
{date_line()}
{line("시각", ("KST", ["09시","15시","21시","03시"]), "|", ("걸린 시간 십분", ["1","2","3","4","5","6"]))}
{line("등압선", ("모양·간격", ["상","중","하"]), "|", ("고기압 중심", G))}
{line("저기압", ("중심", G), "|", ("전선", ["맞음","일부","놓침","없는데 그림"]))}
</div>'''
deep = page("섀도 TAF 채점 · 일기도 채점 시트", "T1",
    "W1에 칠한 섀도 TAF를 나중에 채점하는 시트. 같은 날짜·지점의 TAF 기록에 심층·틀린 원인이 붙음. 「심층 완료」는 일기도·Skew-T 등 열어서 원인까지 분석했을 때만.",
    deep_block(1) + deep_block(2) + deep_block(3) + chart_block(), "T1 · TAF 3 + 일기도 1")

html = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{study}{wx}{exam}{deep}</body></html>'
(OUT / "sheets.html").write_text(html, encoding="utf-8")

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto((OUT / "sheets.html").resolve().as_uri()); pg.wait_for_timeout(500)
    pg.pdf(path=str(OUT / "체크시트.pdf"), format="A4", print_background=True, prefer_css_page_size=True)
    pg.set_viewport_size({"width": 794, "height": 1123})
    for i, el in enumerate(pg.query_selector_all(".page")):
        el.screenshot(path=str(OUT / f"preview{i+1}.png"))
    b.close()
print("ok")
