"""오늘의 출력: 지상 손 분석용 관측소 기입도 + METAR 해독 연습 + 정답(자동 등압선).

사용: python scripts/daily_wx.py [출력 PDF 경로] [YYYY-MM-DDTHHZ]
기본: 가장 최근 00Z(09시 KST) 관측, site/today.pdf
데이터: aviationweather.gov METAR/TAF API
"""
import json, sys, urllib.request, datetime as dt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import font_manager
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from metpy.plots import StationPlot, sky_cover, current_weather, wx_code_to_numeric
from metpy.calc import reduce_point_density
from metpy.interpolate import interpolate_to_grid

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f or "NotoSansKR" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["Noto Sans CJK KR", "Noto Sans CJK JP", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

API = "https://aviationweather.gov/api/data"
BBOX = (22, 108, 50, 150)  # 남, 서, 북, 동
EXTENT = (112, 147, 25, 47)
KST = dt.timezone(dt.timedelta(hours=9))
PRACTICE = ["RKPK", "RKSI", "RKSS", "RKPC", "RKJB", "RKTU", "RKNY", "RKSO"]
COVER = {"SKC": 0, "CLR": 0, "NSC": 0, "CAVOK": 0, "FEW": 2, "SCT": 4, "BKN": 6, "OVC": 8, "OVX": 9}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "study-dashboard"})
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode()
    return body


def target_time(arg=None):
    if arg:
        return dt.datetime.strptime(arg, "%Y-%m-%dT%HZ").replace(tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    t = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now - t < dt.timedelta(minutes=40):
        t -= dt.timedelta(days=1)
    return t


def fetch_obs(t):
    end = t + dt.timedelta(minutes=30)
    url = (f"{API}/metar?bbox={','.join(map(str, BBOX))}&format=json&hours=1"
           f"&date={end:%Y%m%d_%H%M}")
    data = json.loads(get(url) or "[]")
    best = {}
    for o in data:
        dtime = abs(o["obsTime"] - t.timestamp())
        if dtime > 35 * 60:
            continue
        if o["icaoId"] not in best or dtime < best[o["icaoId"]][0]:
            best[o["icaoId"]] = (dtime, o)
    return [v[1] for v in best.values()]


def fetch_taf(station):
    try:
        return get(f"{API}/taf?ids={station}&format=raw").strip()
    except Exception:
        return ""


KMA = "https://apihub.kma.go.kr/api/typ01/url"
SFCTM_COLS = ("TM STN WD WS GST_WD GST_WS GST_TM PA PS PT PR TA TD HM PV RN RN_DAY RN_JUN RN_INT SD_HR3 SD_DAY "
              "SD_TOT WC WP WW CA_TOT CA_MID CH_MIN CT CT_TOP CT_MID CT_LOW VS SS SI ST_GD TS").split()


def _kma_rows(text):
    return [ln.split() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def fetch_kma(t, key):
    """기상청 API허브 ASOS(지상관측) 정시 자료 → METAR와 같은 모양의 dict 목록. 해면기압(PS) 사용."""
    if not key:
        return []
    tm = t.astimezone(KST).strftime("%Y%m%d%H%M")
    body = get(f"{KMA}/kma_sfctm2.php?tm={tm}&stn=0&help=0&authKey={key}")
    print("기상청 시간자료 OK:", len(_kma_rows(body)), "줄")
    inf = get(f"{KMA}/stn_inf.php?inf=SFC&stn=&tm={tm}&help=0&authKey={key}")
    loc = {}
    for r in _kma_rows(inf):
        try:
            loc[r[0]] = (float(r[1]), float(r[2]), r[-1] if not r[-1].replace(".", "").isdigit() else r[0])
        except (ValueError, IndexError):
            pass
    cols = SFCTM_COLS
    for ln in body.splitlines():  # 헤더에 열 이름 줄이 있으면 그걸 우선
        tok = ln.lstrip("# ").split()
        if "STN" in tok and "PS" in tok and "TA" in tok:
            cols = ["TM" if c.startswith("YYMM") else c for c in tok]
    out = []
    for r in _kma_rows(body):
        row = dict(zip(cols, r))
        stn = row.get("STN")
        if stn not in loc:
            continue
        f = lambda k: (lambda x: np.nan if x is None or x <= -9 else x)(num(row.get(k)))
        ps = f("PS")
        if not np.isfinite(ps) or ps < 900:
            continue
        ca = f("CA_TOT")
        lon, lat, name = loc[stn]
        out.append({"icaoId": f"ASOS{stn}", "name": name, "lon": lon, "lat": lat, "temp": f("TA"), "dewp": f("TD"),
                    "altim": ps, "wdir": f("WD"), "wspd": f("WS") * 1.944 if np.isfinite(f("WS")) else np.nan,
                    "clouds": [] if not np.isfinite(ca) else [{"cover": ["SKC", "FEW", "FEW", "SCT", "SCT", "SCT", "BKN", "BKN", "BKN", "BKN", "OVC"][int(ca)]}],
                    "cover": None if np.isfinite(ca) else "?", "wxString": ""})
    return out


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def prep(obs):
    lon = np.array([o["lon"] for o in obs]); lat = np.array([o["lat"] for o in obs])
    t = np.array([num(o.get("temp")) for o in obs]); td = np.array([num(o.get("dewp")) for o in obs])
    p = np.array([num(o.get("altim")) for o in obs])
    wdir = np.array([np.nan if o.get("wdir") in (None, "VRB") else num(o.get("wdir")) for o in obs])
    wspd = np.array([num(o.get("wspd")) for o in obs])
    u = -wspd * np.sin(np.radians(wdir)); v = -wspd * np.cos(np.radians(wdir))
    u[np.isnan(u)] = 0; v[np.isnan(v)] = 0
    cov = []
    for o in obs:
        cs = [COVER.get(c.get("cover"), 0) for c in (o.get("clouds") or [])]
        cov.append(min(max(cs), 8) if cs else (0 if o.get("cover") in ("CAVOK", "CLR", "SKC", "NSC") else 10))
    wx = wx_code_to_numeric([o.get("wxString") or "" for o in obs])
    ids = [o["icaoId"] for o in obs]
    return dict(lon=lon, lat=lat, t=t, td=td, p=p, u=u, v=v, cov=np.array(cov), wx=wx, ids=ids)


def base_map(fig, rect, title):
    proj = ccrs.LambertConformal(central_longitude=128, central_latitude=36, standard_parallels=(30, 60))
    ax = fig.add_axes(rect, projection=proj)
    ax.set_extent(EXTENT, ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#f7f6f2")
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#ffffff")
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.5, edgecolor="#777")
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), linewidth=0.3, edgecolor="#aaa", linestyle=":")
    gl = ax.gridlines(draw_labels=False, linewidth=0.2, color="#ccc", xlocs=range(100, 160, 5), ylocs=range(20, 55, 5))
    ax.set_title(title, fontsize=10, loc="left")
    return ax, proj


def station_plot(ax, proj, d, radius_km=170):
    xy = proj.transform_points(ccrs.PlateCarree(), d["lon"], d["lat"])[:, :2]
    pri = np.array([0 if i.startswith(("RK", "ASOS")) else 1 for i in d["ids"]])
    keep = reduce_point_density(xy, radius_km * 1000, priority=-pri.astype(float)) if len(xy) else []
    inside = (d["lon"] > EXTENT[0] + .5) & (d["lon"] < EXTENT[1] - .5) & (d["lat"] > EXTENT[2] + .3) & (d["lat"] < EXTENT[3] - .3)
    keep = keep & np.isfinite(d["p"]) & inside if len(xy) else keep
    s = {k: (np.array(v)[keep] if k != "ids" else [x for x, k2 in zip(v, keep) if k2]) for k, v in d.items() if k != "src"}
    from metpy.plots.wx_symbols import wx_symbol_font
    pxy = proj.transform_points(ccrs.PlateCarree(), s["lon"], s["lat"])[:, :2]
    ax.barbs(pxy[:, 0], pxy[:, 1], s["u"], s["v"], length=5.2, linewidth=0.5, transform=proj, zorder=4)
    fs = 6.2
    def put(x, y, txt, dx, dy, ha, va, **kw):
        ax.annotate(txt, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=fs, zorder=5, **kw)
    for k, (x, y) in enumerate(pxy):
        if np.isfinite(s["t"][k]): put(x, y, f"{s['t'][k]:.0f}", -5, 3, "right", "bottom", color="#c0392b")
        if np.isfinite(s["td"][k]): put(x, y, f"{s['td'][k]:.0f}", -5, -3, "right", "top", color="#1e7a46")
        if np.isfinite(s["p"][k]): put(x, y, format(int(round(s["p"][k] * 10)) % 1000, "03d"), 5, 3, "left", "bottom", color="#222")
        ax.annotate(sky_cover(int(s["cov"][k])), (x, y), ha="center", va="center", fontsize=8.5, zorder=6,
                    fontproperties=wx_symbol_font, bbox=None)
        w = int(s["wx"][k]) if np.isfinite(s["wx"][k]) else 0
        if w > 0:
            ax.annotate(current_weather(w), (x, y), xytext=(-8, 0), textcoords="offset points", ha="right", va="center",
                        fontsize=8, color="#1a5fb4", fontproperties=wx_symbol_font, zorder=6)
        if s["ids"][k] in PRACTICE:
            put(x, y, s["ids"][k], 0, -9, "center", "top", color="#999", )
    return int(np.sum(keep))


def page_map(pdf, d, t):
    fig = plt.figure(figsize=(11.69, 8.27))
    title = f"오늘의 출력 ① 지상 손 분석   {t.astimezone(KST):%Y-%m-%d %H}시 KST ({t:%H}Z)"
    ax, proj = base_map(fig, [0.03, 0.08, 0.72, 0.86], title)
    n = station_plot(ax, proj, d)
    fig.text(0.77, 0.90, "할 일 (20~30분)", fontsize=11, weight="bold")
    steps = [
        "1. 기압(오른쪽 위 3자리)을 훑어서\n   가장 높은 곳·낮은 곳에 H, L 표시",
        "2. 등압선을 4hPa 간격으로 연필로\n   (1000, 1004, 1008 … 1032, 1036)",
        "   · 숫자 사이를 비례로 끊어서\n   · 선끼리 절대 교차하지 않게",
        "3. 바람 깃(꼬리)이 등압선을 가로질러\n   저압 쪽으로 기우는지 확인",
        "4. 기온이 급하게 바뀌고 바람이 꺾이는\n   곳이 있으면 전선 후보로 표시",
        "5. 한반도 날씨를 한 줄로 예측:\n   내일 오산·김해 바람/기온/구름",
        "",
        "기입 읽는 법",
        "  빨강 = 기온(°C)    초록 = 이슬점",
        "  오른쪽 위 = 기압 끝 3자리 ×10",
        "     예) 290 → 1029.0 hPa",
        "     예) 985 → 998.5 hPa",
        "  원 = 운량 (빈 원 맑음 → 꽉 참 흐림)",
        "  파란 기호 = 현재 날씨",
        "  깃: 짧은 깃 5kt, 긴 깃 10kt, 삼각 50kt",
        "",
        f"관측소 {n}개 · {d['src']}",
        "공식 분석: 날씨누리 → 날씨 → 일기도 → 분석일기도",
        "정답(자동 등압선)은 3쪽 — 다 그리고 볼 것",
        "다 그리면 사진 → 드라이브 「기록함」",
    ]
    fig.text(0.77, 0.86, "\n".join(steps), fontsize=8.2, va="top", linespacing=1.55)
    pdf.savefig(fig); plt.close(fig)


def page_metar(pdf, obs, t, taf):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.07, 0.955, f"오늘의 출력 ② METAR 해독   {t.astimezone(KST):%Y-%m-%d %H}시 KST", fontsize=13, weight="bold")
    fig.text(0.07, 0.935, "원문만 보고 표를 채우기. 단위: 풍속 kt, 시정 m(9999 = 10km 이상), 운고 ft(×100), 기온 °C, QNH hPa", fontsize=8, color="#555")
    by = {o["icaoId"]: o for o in obs}
    picks = [by[s] for s in PRACTICE if s in by][:5]
    y = 0.90
    cols = ["풍향/풍속", "시정", "현천", "구름(양·높이)", "기온/이슬점", "QNH"]
    for o in picks:
        fig.text(0.07, y, o["rawOb"], fontsize=8.6, family="monospace")
        y -= 0.022
        x0, w = 0.07, 0.86 / len(cols)
        for i, c in enumerate(cols):
            fig.add_artist(plt.Rectangle((x0 + i * w, y - 0.045), w, 0.045, fill=False, lw=0.6, transform=fig.transFigure))
            fig.text(x0 + i * w + 0.005, y - 0.012, c, fontsize=6.6, color="#777")
        y -= 0.075
    if taf:
        fig.text(0.07, y, "섀도 TAF 비교용 — 김해 공식 TAF (내 예보를 먼저 W1 시트에 칠하고 볼 것)", fontsize=9, weight="bold")
        y -= 0.02
        import textwrap
        for line in textwrap.wrap(taf, 92):
            fig.text(0.07, y, line, fontsize=7.6, family="monospace"); y -= 0.016
        y -= 0.015
    fig.text(0.07, y, "오늘의 질문 (한 줄씩)", fontsize=9, weight="bold"); y -= 0.022
    qs = ["1. 한반도 주변 등압선 간격이 좁은 곳은? → 바람이 가장 강한 곳과 일치하나?",
          "2. 지금 한반도는 어느 고기압/저기압의 영향권? 그래서 바람 방향은?",
          "3. 기온-이슬점 차이가 3°C 이하인 관측소는? 내일 아침 안개 가능성?"]
    for q in qs:
        fig.text(0.07, y, q, fontsize=8.4); y -= 0.035
    pdf.savefig(fig); plt.close(fig)
    return picks


def decode(o):
    wd = o.get("wdir"); ws = o.get("wspd"); g = o.get("wgst")
    wind = "무풍" if ws in (0, None) else f"{wd}° {ws}kt" + (f" G{g}" if g else "")
    cl = ", ".join(f"{c['cover']} {c.get('base') or ''}" for c in (o.get("clouds") or [])) or (o.get("cover") or "-")
    raw = o["rawOb"]
    import re
    m = re.search(r" (\d{4}) ", raw)
    vis = ("10km 이상" if m and m.group(1) == "9999" else f"{int(m.group(1))}m") if m else (f"{o.get('visib')} SM" if o.get("visib") else "-")
    if "CAVOK" in raw: vis = "CAVOK (10km+)"
    return [wind, vis, o.get("wxString") or "없음", cl, f"{o.get('temp')}/{o.get('dewp')}", str(o.get("altim"))]


def page_answer(pdf, d, picks, t):
    fig = plt.figure(figsize=(11.69, 8.27))
    ax, proj = base_map(fig, [0.03, 0.08, 0.62, 0.86], "③ 정답: 자동 분석 등압선 (4hPa) — 손 분석 끝내고 비교")
    ok = np.isfinite(d["p"])
    xy = proj.transform_points(ccrs.PlateCarree(), d["lon"][ok], d["lat"][ok])[:, :2]
    gx, gy, gp = interpolate_to_grid(xy[:, 0], xy[:, 1], d["p"][ok], interp_type="barnes",
                                     hres=60000, minimum_neighbors=3, search_radius=500000, gamma=0.25)
    from scipy.spatial import cKDTree
    dist, _ = cKDTree(xy).query(np.column_stack([gx.ravel(), gy.ravel()]))
    gp = np.ma.masked_where((dist.reshape(gx.shape) > 260000) | np.ma.getmaskarray(gp), gp)
    levels = np.arange(960, 1060, 4)
    cs = ax.contour(gx, gy, gp, levels=levels, colors="#1a5fb4", linewidths=0.9, transform=proj)
    ax.clabel(cs, fmt="%d", fontsize=6)
    station_plot(ax, proj, d, radius_km=230)
    try:
        from scipy.ndimage import maximum_filter, minimum_filter
        g = np.ma.filled(gp.astype(float), np.nan)
        for flt, lab, col in ((maximum_filter, "H", "#1a5fb4"), (minimum_filter, "L", "#c0392b")):
            ext = flt(np.nan_to_num(g, nan=(-1e9 if lab == "H" else 1e9)), size=15)
            idx = np.argwhere((g == ext) & np.isfinite(g))
            placed = []
            for i, j in idx:
                if any((gx[i, j] - a) ** 2 + (gy[i, j] - b) ** 2 < 900000 ** 2 for a, b in placed):
                    continue
                placed.append((gx[i, j], gy[i, j]))
                if 3 < i < g.shape[0] - 4 and 3 < j < g.shape[1] - 4:
                    ax.text(gx[i, j], gy[i, j], lab, transform=proj, fontsize=16, weight="bold", color=col, ha="center", va="center", clip_on=True)
    except Exception:
        pass
    fig.text(0.67, 0.90, "METAR 해독 정답", fontsize=11, weight="bold")
    y = 0.86
    for o in picks:
        row = decode(o)
        fig.text(0.67, y, o["icaoId"], fontsize=8.6, weight="bold"); y -= 0.022
        txt = f"바람 {row[0]} · 시정 {row[1]} · 현천 {row[2]}\n구름 {row[3]} · 기온/이슬점 {row[4]} · QNH {row[5]}"
        fig.text(0.67, y, txt, fontsize=7.6, va="top", linespacing=1.5); y -= 0.065
    fig.text(0.67, 0.12, "자동 등압선은 관측소 사이를 수학적으로 보간한 것이라\n바다 위·관측 드문 곳은 실제와 다를 수 있음.\n공식 분석은 기상청 날씨누리 「분석일기도」와 비교.", fontsize=7.2, color="#555", linespacing=1.5)
    pdf.savefig(fig); plt.close(fig)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "site/today.pdf"
    t = target_time(sys.argv[2] if len(sys.argv) > 2 else None)
    obs = fetch_obs(t)
    if len(obs) < 30:
        t -= dt.timedelta(days=1)
        obs = fetch_obs(t)
    import os
    kma, src = [], "METAR QNH"
    try:
        kma = fetch_kma(t, os.environ.get("KMA_KEY", ""))
    except Exception as e:
        body = getattr(e, "read", lambda: b"")()[:300].decode("utf-8", "replace") if hasattr(e, "read") else ""
        print("기상청 자료 실패, METAR만 사용:", getattr(e, "url", "").split("?")[0], e, body.replace("\n", " "))
    if len(kma) >= 20:
        src = f"한국 = 기상청 ASOS 해면기압 {len(kma)}곳, 해외 = METAR QNH"
        mapobs = [o for o in obs if not o["icaoId"].startswith("RK")] + kma
    else:
        mapobs = obs
    d = prep(mapobs)
    d["src"] = src
    taf = fetch_taf("RKPK")
    with PdfPages(out) as pdf:
        page_map(pdf, d, t)
        picks = page_metar(pdf, obs, t, taf)
        page_answer(pdf, d, picks, t)
    print(f"{out}: {t:%Y-%m-%d %HZ}, METAR {len(obs)}개, 기상청 ASOS {len(kma)}개 · {src}")


if __name__ == "__main__":
    main()
