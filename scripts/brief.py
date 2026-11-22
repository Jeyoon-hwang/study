"""TAF 브리핑 자료 수집 → site/brief/brief.json + 이미지

공항 4곳(사천·김해·제주·청주) 섀도 TAF용:
- 실황: METAR 최근 12시간, 공식 TAF (페이지에서는 가려 둠)
- 위성: 천리안 2A RGB·적외·수증기·안개 (날씨누리), 적외 1시간 애니메이션
- 레이더: 기상청 합성 레이더 최신 + 1시간 애니메이션
- 고층: 가장 가까운 라디오존데(GTS BUFR TEMP) Skew-T + 안정도 지수
- 모델: Open-Meteo로 KMA LDPS/GDPS, ECMWF, GFS, JMA MSM 공항 지점 예측 미티오그램
- SIGMET: 인천 FIR(RKRR)
지상·850·700·500·300hPa 일기도는 kma-charts.mjs가 만든 charts.json을 페이지가 같이 쓴다.

KMA_KEY 환경변수 필요(라디오존데). 하나가 실패해도 나머지는 계속 만든다.
"""
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import datetime as dt
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "brief"
OUT.mkdir(parents=True, exist_ok=True)
KEY = os.environ.get("KMA_KEY", "")
UTC, KST = dt.timezone.utc, dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(UTC)
UA = {"User-Agent": "study-dashboard (TAF brief)"}

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f or "NotoSansKR" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

AIRPORTS = [
    dict(icao="RKPS", name="사천", lat=35.088, lon=128.071, sonde=["47155"]),
    dict(icao="RKPK", name="김해", lat=35.179, lon=128.938, sonde=["47155"]),
    dict(icao="RKPC", name="제주", lat=33.511, lon=126.493, sonde=["47186", "47185"]),
    dict(icao="RKTU", name="청주", lat=36.717, lon=127.499, sonde=["47135", "47104"]),
]
SONDE_NAME = {"47155": "창원", "47186": "제주", "47185": "제주 고산", "47135": "추풍령", "47104": "북강릉"}
SAT = [  # (날씨누리 코드, 이름)
    ("rgb-s-daynight", "RGB 주야간합성"),
    ("rgb-cs", "RGB 구름·지면"),
    ("rgb-hlc", "RGB 상층·하층운"),
    ("ir105", "적외 10.5µm"),
    ("wv063", "수증기 6.3µm"),
    ("fog", "안개"),
]
MODELS = [  # (Open-Meteo 코드, 표시 이름, 색)
    ("kma_ldps", "KMA LDPS", "#d6453d"),
    ("kma_gdps", "KMA GDPS", "#f79009"),
    ("ecmwf_ifs025", "ECMWF", "#2e90fa"),
    ("gfs_seamless", "GFS", "#12b76a"),
    ("jma_msm", "JMA MSM", "#7a5af8"),
]
result = {"updated": NOW.isoformat(), "airports": [], "sat": [], "radar": None, "sigmet": [], "errors": []}


def get(url, binary=False, timeout=60, tries=3):
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type") or ""
            return (data, ctype) if binary else data.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(2 * (i + 1))
    raise err


def note_err(what, e):
    msg = f"{what}: {e}"
    print("실패 —", msg, file=sys.stderr)
    result["errors"].append(msg)


def kst(t):
    return t.astimezone(KST)


# ───────────────────────── 실황: METAR·TAF·SIGMET ─────────────────────────
def obs():
    ids = ",".join(a["icao"] for a in AIRPORTS)
    met, taf = {}, {}
    try:
        for m in json.loads(get(f"https://aviationweather.gov/api/data/metar?ids={ids}&hours=12&format=json")):
            met.setdefault(m["icaoId"], []).append(m.get("rawOb", ""))
    except Exception as e:  # noqa: BLE001
        note_err("METAR", e)
    try:
        for t in json.loads(get(f"https://aviationweather.gov/api/data/taf?ids={ids}&format=json")):
            taf[t["icaoId"]] = t.get("rawTAF", "")
    except Exception as e:  # noqa: BLE001
        note_err("TAF", e)
    try:
        for s in json.loads(get("https://aviationweather.gov/api/data/isigmet?format=json")):
            if (s.get("firId") or "").upper() == "RKRR":
                result["sigmet"].append({"raw": s.get("rawSigmet", ""), "hazard": s.get("hazard"),
                                         "from": s.get("validTimeFrom"), "to": s.get("validTimeTo")})
    except Exception as e:  # noqa: BLE001
        note_err("SIGMET", e)
    return met, taf


# ───────────────────────── 위성 (천리안 2A, 날씨누리) ─────────────────────────
NURI = "https://www.weather.go.kr"


def nuri_list(path, params):
    q = urllib.parse.urlencode(params)
    return json.loads(get(f"{NURI}/w/wnuri-img/rest/{path}?{q}"))


def satellite():
    tm = kst(NOW).strftime("%Y.%m.%d.%H:%M")
    for code, name in SAT:
        try:
            items = nuri_list("sat/images/gk2a.do", {"data": code, "area": "ko", "tm": tm})
            if not items:
                raise RuntimeError("목록 없음")
            it = items[-1]
            data, ctype = get(NURI + it["url"], binary=True)
            if "image" not in ctype:
                raise RuntimeError("이미지 아님")
            img = Image.open(io.BytesIO(data)).convert("RGB")
            if img.width > 1100:
                img = img.resize((1100, round(img.height * 1100 / img.width)))
            fn = f"sat-{code}.jpg"
            img.save(OUT / fn, quality=85)
            entry = {"id": code, "name": name, "file": f"brief/{fn}", "tm": it["tm"]}
            if code == "ir105":  # 최근 ~1시간 애니메이션
                frames = []
                for f in items[-24::4]:
                    try:
                        d2, c2 = get(NURI + f["url"], binary=True)
                        if "image" in c2:
                            im = Image.open(io.BytesIO(d2)).convert("L")
                            frames.append(im.resize((520, round(im.height * 520 / im.width))))
                    except Exception:  # noqa: BLE001
                        pass
                if len(frames) >= 3:
                    frames[0].save(OUT / "sat-ir105-loop.gif", save_all=True, append_images=frames[1:],
                                   duration=[500] * (len(frames) - 1) + [1400], loop=0)
                    entry["loop"] = "brief/sat-ir105-loop.gif"
            result["sat"].append(entry)
            print("위성", code, it["tm"])
        except Exception as e:  # noqa: BLE001
            note_err(f"위성 {code}", e)


# ───────────────────────── 레이더 ─────────────────────────
def radar():
    base = NOW.replace(second=0, microsecond=0)
    base -= dt.timedelta(minutes=base.minute % 5)
    found = []
    for i in range(0, 120, 5):  # 최근 2시간 안에서 이미지가 있는 시각
        t = kst(base - dt.timedelta(minutes=i))
        url = f"http://www.kma.go.kr/repositary/image/rdr/img/RDR_CMP_WRC_{t:%Y%m%d%H%M}.png"
        try:
            data, ctype = get(url, binary=True, timeout=30, tries=2)
            if "image" in ctype and len(data) > 5000:
                found.append((t, data))
                if len(found) >= 7:
                    break
        except Exception:  # noqa: BLE001
            continue
    if not found:
        note_err("레이더", "최근 2시간 이미지 없음")
        return
    t0, d0 = found[0]
    Image.open(io.BytesIO(d0)).convert("RGB").save(OUT / "radar.png")
    frames = [Image.open(io.BytesIO(d)).convert("RGB") for _, d in reversed(found[:7:2])]
    if len(frames) >= 3:
        frames[0].save(OUT / "radar-loop.gif", save_all=True, append_images=frames[1:],
                       duration=[600] * (len(frames) - 1) + [1500], loop=0)
    result["radar"] = {"file": "brief/radar.png", "loop": "brief/radar-loop.gif" if len(frames) >= 3 else None,
                       "tm": f"{t0:%Y%m%d%H%M}"}
    print("레이더", t0)


# ───────────────────────── 라디오존데 Skew-T ─────────────────────────
def parse_temp(raw, stn):
    rows = []
    for ln in raw.decode("euc-kr", "replace").splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        p = ln.split()
        if len(p) < 8 or p[1] != stn:
            continue
        try:
            pa, gh, ta, td, wd, ws = map(float, p[2:8])
        except ValueError:
            continue
        bad = lambda v: v <= -99 or v >= 9990  # noqa: E731
        if bad(pa) or bad(ta) or bad(gh) or pa < 100:
            continue
        rows.append((pa, gh, ta, np.nan if bad(td) else td, np.nan if bad(wd) else wd, np.nan if bad(ws) else ws))
    if len(rows) <= 20:
        return None
    a = np.array(sorted(rows, key=lambda r: -r[0]))
    _, idx = np.unique(-a[:, 0], return_index=True)
    return a[np.sort(idx)]


def fetch_sounding(stn):
    """가장 최근 00/12Z 관측 (없으면 그 전 회차)."""
    t = NOW - dt.timedelta(hours=1, minutes=30)
    t = t.replace(hour=0 if t.hour < 12 else 12, minute=0, second=0, microsecond=0)
    for back in range(3):
        tt = t - dt.timedelta(hours=12 * back)
        url = (f"https://apihub.kma.go.kr/api/typ01/url/gts_bufr_temp.php?"
               f"tm={tt:%Y%m%d%H%M}&stn={stn}&help=0&authKey={KEY}")
        raw, _ = get(url, binary=True, timeout=120)
        a = parse_temp(raw, stn)
        if a is not None:
            return tt, a
    return None, None


def skewt(stn, a, t):
    from metpy.plots import SkewT
    from metpy.units import units
    import metpy.calc as mpcalc

    p, z, T, Td, wd, ws = (a[:, i] for i in range(6))
    P, Tq, Tdq = p * units.hPa, T * units.degC, Td * units.degC
    idx = {}
    ok = ~np.isnan(Td)
    sfc_z = z[0]
    # 지상 기준 파셀
    try:
        lcl_p, lcl_t = mpcalc.lcl(P[0], Tq[0], Tdq[0])
        idx["LCL"] = f"{lcl_p.m:.0f} hPa"
        lcl_z = np.interp(-lcl_p.m, -p, z) - sfc_z
        idx["LCL 고도"] = f"{lcl_z:.0f} m ({lcl_z * 3.281 / 100:.0f}00 ft)"
    except Exception:  # noqa: BLE001
        lcl_p = None
    pm, Tm, Tdm = P[ok], Tq[ok], Tdq[ok]
    prof = None
    try:
        prof = mpcalc.parcel_profile(pm, Tm[0], Tdm[0]).to("degC")
        cape, cin = mpcalc.cape_cin(pm, Tm, Tdm, prof)
        idx["CAPE"] = f"{cape.m:.0f} J/kg"
        idx["CIN"] = f"{cin.m:.0f} J/kg"
        li = mpcalc.lifted_index(pm, Tm, prof)
        idx["LI"] = f"{np.atleast_1d(li.m)[0]:.1f}"
    except Exception:  # noqa: BLE001
        pass
    try:
        idx["K 지수"] = f"{mpcalc.k_index(pm, Tm, Tdm).m:.0f}"
    except Exception:  # noqa: BLE001
        pass
    try:
        idx["가강수량"] = f"{mpcalc.precipitable_water(pm, Tdm).to('mm').m:.0f} mm"
    except Exception:  # noqa: BLE001
        pass
    # 0℃ 고도 (지상에서 처음 0℃ 아래로)
    below = np.where(T <= 0)[0]
    if len(below):
        i = below[0]
        if i == 0:
            idx["0℃ 고도"] = "지상부터 영하"
        else:
            zf = np.interp(0, [T[i], T[i - 1]], [z[i], z[i - 1]]) - sfc_z
            idx["0℃ 고도"] = f"{zf:.0f} m ({zf * 3.281 / 100:.0f}00 ft)"
    # 지상 3km 안 가장 낮은 역전층
    low = (z - sfc_z) <= 3000
    zi, Ti = z[low], T[low]
    inv = None
    for i in range(1, len(Ti)):
        if Ti[i] > Ti[i - 1] + 0.05:
            j = i
            while j + 1 < len(Ti) and Ti[j + 1] >= Ti[j]:
                j += 1
            if Ti[j] - Ti[i - 1] >= 0.5:
                inv = (zi[i - 1] - sfc_z, zi[j] - sfc_z, Ti[j] - Ti[i - 1])
                break
    idx["역전층"] = f"{inv[0]:.0f}~{inv[1]:.0f} m, +{inv[2]:.1f}℃" if inv else "3km 안 없음"
    # 지상~2000ft(약 610m) 바람 차 (저층 윈드시어 감)
    okw = ~np.isnan(ws) & ~np.isnan(wd)
    if okw.sum() > 5:
        zz = z[okw] - sfc_z
        u, v = mpcalc.wind_components(ws[okw] * units("m/s"), wd[okw] * units.deg)
        u, v = u.to("knot").m, v.to("knot").m
        u0, v0 = u[0], v[0]
        u2, v2 = np.interp(610, zz, u), np.interp(610, zz, v)
        idx["지상~2000ft 바람 차"] = f"{np.hypot(u2 - u0, v2 - v0):.0f} kt"
        for lev in (925, 850):
            if p[okw].max() >= lev:
                uu, vv = np.interp(-lev, -p[okw], u), np.interp(-lev, -p[okw], v)
                spd = np.hypot(uu, vv)
                dirn = (np.degrees(np.arctan2(-uu, -vv)) + 360) % 360
                idx[f"{lev}hPa 바람"] = f"{dirn:03.0f}° {spd:.0f} kt"
    # 그림
    fig = plt.figure(figsize=(9, 6.4), dpi=110)
    sk = SkewT(fig, rotation=45, rect=(0.08, 0.08, 0.6, 0.86), aspect="auto")
    sk.plot(P, Tq, "#d6453d", lw=1.8, label="기온")
    sk.plot(pm, Tdm, "#12b76a", lw=1.8, label="이슬점")
    if prof is not None:
        sk.plot(pm, prof, "k", lw=1.1, ls="--", label="지상 파셀")
        try:
            sk.shade_cape(pm, Tm, prof, alpha=0.2)
            sk.shade_cin(pm, Tm, prof, Tdm, alpha=0.15)
        except Exception:  # noqa: BLE001
            pass
    if lcl_p is not None:
        sk.ax.axhline(lcl_p.m, color="#475467", lw=0.8, ls=":")
        sk.ax.text(-33, lcl_p.m, " LCL", va="bottom", fontsize=8, color="#475467")
    sk.plot_dry_adiabats(alpha=0.18, lw=0.7)
    sk.plot_moist_adiabats(alpha=0.18, lw=0.7)
    sk.plot_mixing_lines(alpha=0.18, lw=0.7)
    sk.ax.axvline(0, color="#2e90fa", lw=0.8, alpha=0.6)
    bi = np.where(okw)[0]
    if len(bi):
        sel, lastp = [], 9999
        for i in bi:
            if lastp - p[i] >= 25:
                sel.append(i)
                lastp = p[i]
        ub, vb = mpcalc.wind_components(ws[sel] * units("m/s"), wd[sel] * units.deg)
        sk.plot_barbs(P[sel], ub.to("knot"), vb.to("knot"), xloc=1.04, length=6)
    sk.ax.set_ylim(1050, 200)
    sk.ax.set_xlim(-35, 35)
    sk.ax.set_xlabel("℃")
    sk.ax.set_ylabel("hPa")
    sk.ax.legend(loc="upper right", fontsize=8, framealpha=0.85)
    kt = kst(t)
    sk.ax.set_title(f"{SONDE_NAME.get(stn, stn)} ({stn})  {t:%m/%d %HZ} · {kt:%H}시 KST", fontsize=11, loc="left")
    txt = "\n".join(f"{k}: {v}" for k, v in idx.items())
    fig.text(0.755, 0.94, txt, fontsize=8.2, va="top", linespacing=1.7,
             bbox=dict(boxstyle="round,pad=0.5", fc="#f9fafb", ec="#d0d5dd"))
    fn = f"skewt-{stn}.png"
    fig.savefig(OUT / fn)
    plt.close(fig)
    return {"stn": stn, "name": SONDE_NAME.get(stn, stn), "tm": t.isoformat(), "file": f"brief/{fn}", "idx": idx}


# ───────────────────────── 모델 미티오그램 (Open-Meteo) ─────────────────────────
def meteogram(ap):
    vars_ = ["temperature_2m", "dew_point_2m", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
             "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "visibility", "precipitation"]
    q = urllib.parse.urlencode({
        "latitude": ap["lat"], "longitude": ap["lon"], "hourly": ",".join(vars_),
        "models": ",".join(m for m, _, _ in MODELS), "forecast_hours": 36,
        "wind_speed_unit": "kn", "timezone": "Asia/Seoul",
    })
    d = json.loads(get(f"https://api.open-meteo.com/v1/forecast?{q}"))["hourly"]
    times = [dt.datetime.fromisoformat(x) for x in d["time"]]
    arr = lambda v, m: np.array([np.nan if x is None else x for x in d.get(f"{v}_{m}", [None] * len(times))], float)  # noqa: E731
    fig, axs = plt.subplots(5, 1, figsize=(9, 10.5), dpi=100, sharex=True,
                            gridspec_kw={"height_ratios": [1.1, 1.0, 0.8, 0.8, 0.6]})
    have = []
    for m, nm, c in MODELS:
        T, Td = arr("temperature_2m", m), arr("dew_point_2m", m)
        if np.all(np.isnan(T)):
            continue
        have.append((m, nm, c))
    n = len(have)
    for k, (m, nm, c) in enumerate(have):
        axs[0].plot(times, arr("temperature_2m", m), color=c, lw=1.7, label=nm)
        axs[0].plot(times, arr("dew_point_2m", m), color=c, lw=1.0, ls="--")
        axs[1].plot(times, arr("wind_speed_10m", m), color=c, lw=1.7)
        axs[1].plot(times, arr("wind_gusts_10m", m), color=c, lw=0.8, ls=":")
        axs[2].plot(times, arr("cloud_cover_low", m), color=c, lw=1.7)
        vis = arr("visibility", m)
        if not np.all(np.isnan(vis)):
            axs[3].plot(times, np.clip(vis / 1000, 0, 10), color=c, lw=1.7)
        w = dt.timedelta(minutes=50 / max(n, 1))
        axs[4].bar(np.array(times) + w * (k - (n - 1) / 2), arr("precipitation", m), width=w, color=c)
    # 풍향 화살표(바람이 불어가는 쪽): 첫 번째로 있는 모델
    if have:
        m, nm, c = have[0]
        wd = arr("wind_direction_10m", m)
        top = max(axs[1].get_ylim()[1], 10)
        axs[1].set_ylim(0, top * 1.25)
        xs = [matplotlib.dates.date2num(times[i]) for i in range(0, len(times), 3) if not np.isnan(wd[i])]
        ds = [np.radians(wd[i]) for i in range(0, len(times), 3) if not np.isnan(wd[i])]
        axs[1].quiver(xs, [top * 1.12] * len(xs), [-np.sin(r) for r in ds], [-np.cos(r) for r in ds],
                      color=c, scale=45, width=0.003, pivot="middle")
    axs[0].set_ylabel("기온·이슬점 ℃")
    axs[1].set_ylabel("바람 kt")
    axs[2].set_ylabel("하층운 %")
    axs[2].set_ylim(0, 105)
    axs[3].set_ylabel("시정 km")
    axs[3].set_ylim(0, 10.5)
    for lim, col in ((5, "#f79009"), (1.6, "#d6453d")):
        axs[3].axhline(lim, color=col, lw=0.8, ls="--")
    axs[4].set_ylabel("강수 mm/h")
    notes = ["실선 기온 / 점선 이슬점", "실선 평균풍속 / 점선 돌풍 / 화살표 = 바람이 불어가는 쪽",
             "지상~약 2km 구름양", "주황 5km · 빨강 1.6km 선", ""]
    for ax, nt in zip(axs, notes):
        ax.grid(alpha=0.25)
        if nt:
            ax.text(0.995, 0.97, nt, transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#475467",
                    bbox=dict(fc="white", ec="none", alpha=0.8, pad=1.5))
        for t in times:
            if t.hour == 0:
                ax.axvline(t, color="#98a2b3", lw=0.8)
    axs[4].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d일\n%H시"))
    axs[4].xaxis.set_major_locator(matplotlib.dates.HourLocator(byhour=range(0, 24, 3)))
    fig.suptitle(f"{ap['icao']} {ap['name']} — 모델 비교 (KST, 앞으로 36시간)", x=0.01, ha="left", fontsize=12)
    fig.legend(*axs[0].get_legend_handles_labels(), ncol=5, fontsize=9, loc="upper right", frameon=False,
               bbox_to_anchor=(0.99, 0.995))
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fn = f"meteo-{ap['icao']}.png"
    fig.savefig(OUT / fn)
    plt.close(fig)
    return {"file": f"brief/{fn}", "models": [nm for _, nm, _ in have]}


def main():
    met, taf = obs()
    satellite()
    radar()
    sondes = {}
    for ap in AIRPORTS:
        e = {"icao": ap["icao"], "name": ap["name"], "metar": met.get(ap["icao"], []), "taf": taf.get(ap["icao"], "")}
        if KEY:
            for stn in ap["sonde"]:
                if stn not in sondes:
                    try:
                        t, a = fetch_sounding(stn)
                        sondes[stn] = skewt(stn, a, t) if a is not None else None
                        print("존데", stn, t)
                    except Exception as ex:  # noqa: BLE001
                        note_err(f"존데 {stn}", ex)
                        sondes[stn] = None
                if sondes.get(stn):
                    e["sonde"] = sondes[stn]
                    break
        try:
            e["model"] = meteogram(ap)
            print("모델", ap["icao"], e["model"]["models"])
        except Exception as ex:  # noqa: BLE001
            note_err(f"모델 {ap['icao']}", ex)
        result["airports"].append(e)
    (OUT / "brief.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("오류", len(result["errors"]), result["errors"])


if __name__ == "__main__":
    main()
