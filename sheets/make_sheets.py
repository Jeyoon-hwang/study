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
MINS = ["00","10","20","30","40","50"]
def study_block(n):
    return f'''<div class="blk"><h3><span>세션 {n}</span><span style="font-weight:500;font-size:6.8pt">안 쓴 세션은 비워두기</span></h3>
{line("과목", SUBJ)}
{line("장·강", ("십", ["0","1","2","3","4"]), ("일", D10), "|", ("이 장 끝", ["완료"]), "|", ("종류", ["개념","예제","연습","Review","기출"]))}
{line("시작", ("시", HOURS), "|", ("분", MINS))}
{line("끝", ("시", HOURS), "|", ("분", MINS))}
{line("푼 문제", ("십", D10), "|", ("일", D10))}
{line("맞은 문제", ("십", D10), "|", ("일", D10))}
</div>'''

study = page("공부 체크 시트", "S1",
    "동그라미를 꽉 칠해. 체크·X 표시 말고 칠하기. 잘못 칠하면 크게 X 긋고 옆에 다시 칠해. 시간은 10분 단위로 가까운 쪽.",
    date_line() + '<div style="height:2mm"></div>' + "".join(study_block(i) for i in range(1, 5)),
    "S1 · 세션 4개 · 모자라면 2장")

# ---------- 기상 시트 (W1) ----------
STN = ["RKPK 김해","RKSI 인천","RKSS 김포","RKSO 오산","RKPC 제주","RKJB 무안"]
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

html = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{study}{wx}</body></html>'
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
