"""소상공인시장진흥공단 상가(상권)정보로 식당 목록을 넓힙니다.

data.go.kr 15083033 (이용허락범위 제한 없음). 영업 중인 상가의 이름, 업종, 주소, 좌표가 있어요.
직접 모은 맛집 후보는 그대로 두고, 같은 식당을 찾으면 좌표를 채우고, 나머지 식당은 src="public"으로 더합니다.

    python scripts/import_public.py            # 공공데이터포털에서 내려받기
    python scripts/import_public.py 파일.zip    # 받아둔 파일 사용
"""
import collections
import csv
import io
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PAGE = "https://www.data.go.kr/data/15083033/fileData.do"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) sejong-lunch-data-import", "Referer": PAGE}

SEJONG_DONGS = ["어진동", "나성동", "도담동", "보람동", "아름동", "종촌동", "고운동", "새롬동", "다정동", "한솔동", "대평동", "소담동", "반곡동", "집현동"]


def nearest_area(lat, lng, centers):
    return min(centers, key=lambda a: (centers[a][0] - lat) ** 2 + (centers[a][1] - lng) ** 2)


REGIONS = [
    {"file": "places.json", "member": "세종", "strip": r"(세종특별자치시|세종시|세종)",
     "keep": lambda r: r["법정동명"] in SEJONG_DONGS, "area": lambda r, c: r["법정동명"], "centers": None},
    {"file": "yeouido.json", "member": "서울", "strip": r"(여의도)",
     "keep": lambda r: r["시군구명"] == "영등포구" and r["법정동명"] == "여의도동",
     "area": lambda r, c: nearest_area(float(r["위도"]), float(r["경도"]), c),
     # index.html의 center와 같은 값이에요.
     "centers": {"국회·서여의도": (37.5272, 126.9192), "여의도역·IFC": (37.5235, 126.9250), "증권가": (37.5222, 126.9285),
                 "여의나루": (37.5262, 126.9322), "샛강·63": (37.5180, 126.9315)}},
]


def get(url, data=None):
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=120)


def download():
    html = get(PAGE).read().decode("utf-8", "replace")
    pk = re.search(r"uddi:[0-9a-fA-F-]{36}(?:_[0-9]+)?", html)
    if not pk:
        raise SystemExit("페이지에서 파일 식별자를 찾지 못했어요:\n" + html[:1500])
    q = urllib.parse.urlencode({"publicDataPk": "15083033", "publicDataDetailPk": pk.group(0), "fileDetailSn": "1"})
    info = json.load(get("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?" + q))
    print("파일 정보 키:", list(info)[:15])
    detail = info.get("fileDataRegistVO") or info.get("dataSetFileDetailInfo") or info
    fid = detail.get("atchFileId")
    sn = detail.get("fileDetailSn", 1)
    if not fid:
        raise SystemExit("다운로드 주소를 찾지 못했어요: " + json.dumps(info, ensure_ascii=False)[:1500])
    url = f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={fid}&fileDetailSn={sn}"
    path = os.path.join(tempfile.gettempdir(), "stores.zip")
    with get(url) as res, open(path, "wb") as out:
        while True:
            chunk = res.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    print("내려받음:", os.path.getsize(path) // (1 << 20), "MB")
    return path


def fix_name(n):
    """zip 안의 한글 파일 이름이 깨졌을 때 되돌립니다."""
    try:
        return n.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return n


def rows_of(z, keyword):
    names = [n for n in z.namelist() if n.lower().endswith(".csv")]
    decoded = {n: fix_name(n) for n in names}
    picked = [n for n in names if keyword in decoded[n]]
    if not picked:
        raise SystemExit(f"'{keyword}' 파일이 없어요: {list(decoded.values())[:25]}")
    print("읽는 파일:", [decoded[n] for n in picked])
    rows = []
    for n in picked:
        raw = z.read(n)
        for enc in ("utf-8-sig", "cp949"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        rows.extend(csv.DictReader(io.StringIO(text)))
    if rows:
        print("컬럼:", list(rows[0])[:45])
    return rows


EXCLUDE = re.compile(r"커피|카페|제과|빵|아이스크림|빙수|음료|주스|주점|호프|맥주|구내식당|도시락|반찬|떡|디저트|요거트|편의점|단체급식")


def category(mid, sub):
    """우리 분류로 바꿉니다. 점심 식당이 아니면 None."""
    if EXCLUDE.search(f"{mid} {sub}".replace("떡볶이", "")):
        return None
    if re.search(r"곱창|족발|보쌈|고기|갈비|삼겹|구이/찜", sub) and "해산물" not in sub and "생선" not in sub:
        return "고기"
    if re.search(r"횟집|해산물|생선|회/|복어|조개", sub):
        return "해산물"
    if re.search(r"김밥|분식|떡볶이|만두", sub):
        return "분식"
    if "일식" in mid:
        return "일식"
    if "중식" in mid:
        return "중식"
    if re.search(r"동남아|베트남|태국|인도|아시아", mid + sub):
        return "아시아"
    if re.search(r"서양식|피자|햄버거|버거|파스타|스테이크|샌드위치", mid + sub):
        return "양식"
    if "한식" in mid:
        return "한식"
    return "기타"


def norm(s, strip):
    s = re.sub(r"\s+", "", s or "")
    s = re.sub(strip, "", s)
    s = re.sub(r"[()&·+,.\-_'\"]", "", s)
    return re.sub(r"(본점|직영점|점)$", "", s)


def road_key(address):
    m = re.search(r"([가-힣0-9]+(?:대로|로|길))\s+([0-9]+(?:-[0-9]+)?)(?![0-9]*(?:층|호))", address or "")
    return f"{m.group(1)} {m.group(2)}" if m else None


def road_of(row):
    return road_key(row.get("도로명주소", ""))


def merge_region(region, rows):
    path = os.path.join(DATA, region["file"])
    old = json.load(open(path, encoding="utf-8"))
    curated = [p for p in old if p.get("src") != "public"]
    strip = region["strip"]

    food, cats, subs, skipped = [], collections.Counter(), collections.Counter(), collections.Counter()
    by_addr = collections.defaultdict(list)
    for r in rows:
        if r.get("상권업종대분류명") != "음식" or not region["keep"](r):
            continue
        try:
            r["_ll"] = (round(float(r["위도"]), 6), round(float(r["경도"]), 6))
        except (TypeError, ValueError):
            continue
        k = road_of(r)
        if k:
            by_addr[k].append(r)
        c = category(r.get("상권업종중분류명", ""), r.get("상권업종소분류명", ""))
        subs[f'{r.get("상권업종중분류명", "")}>{r.get("상권업종소분류명", "")}={c}'] += 1
        if c is None:
            skipped[r.get("상권업종소분류명", "")] += 1
            continue
        r["_cat"] = c
        r["_n"] = norm(r.get("상호명", ""), strip)
        r["_nb"] = norm((r.get("상호명", "") or "") + (r.get("지점명", "") or ""), strip)
        food.append(r)
        cats[c] += 1

    used, res = set(), collections.Counter()
    for p in curated:
        for k in ("lat", "lng", "kakaoAddr", "kakaoName", "geo", "publicName", "publicAddr"):
            p.pop(k, None)
        n = norm(p["name"], strip)
        key = road_key(p.get("address"))
        exact = [r for r in food if n and n in (r["_n"], r["_nb"])]
        close = [r for r in food if len(n) >= 3 and len(r["_n"]) >= 3 and (n in r["_nb"] or r["_n"] in n)]
        hit = None
        if key:
            hit = next((r for r in exact + close if road_of(r) == key), None)
        if not hit and len(exact) == 1:
            hit = exact[0]
        if not hit and not key and len(close) == 1:
            hit = close[0]
        if hit:
            used.add(hit["상가업소번호"])
            p.update(lat=hit["_ll"][0], lng=hit["_ll"][1], geo="public", publicName=hit.get("상호명", ""),
                     publicAddr=hit.get("도로명주소", ""))
            res["같은 식당 찾음"] += 1
        elif key and by_addr.get(key):
            r = by_addr[key][0]
            p.update(lat=r["_ll"][0], lng=r["_ll"][1], geo="addr")
            res["같은 건물 좌표"] += 1
        else:
            p["geo"] = "miss"
            res["못 찾음"] += 1
        if region["centers"] and "lat" in p:
            p["area"] = nearest_area(p["lat"], p["lng"], region["centers"])

    names = {norm(p["name"], strip) for p in curated}
    added, seen, dup = [], set(), 0
    for r in food:
        if r["상가업소번호"] in used:
            continue
        sig = (r["_nb"], road_of(r))
        if sig in seen or (r["_n"] in names and road_of(r) is None):
            dup += 1
            continue
        seen.add(sig)
        name = " ".join(x for x in ((r.get("상호명") or "").strip(), (r.get("지점명") or "").strip()) if x)
        added.append({"id": "sg-" + r["상가업소번호"], "src": "public", "name": name[:40],
                      "area": region["area"](r, region["centers"]), "category": r["_cat"], "price": "",
                      "address": r.get("도로명주소") or r.get("지번주소") or "", "note": r.get("상권업종소분류명", ""),
                      "lat": r["_ll"][0], "lng": r["_ll"][1], "geo": "public"})
    added.sort(key=lambda x: x["id"])
    out = curated + added
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in out) + "\n]\n")
    print(f"\n=== {region['file']}: 맛집 후보 {len(curated)} {dict(res)} · 새로 추가 {len(added)} · 중복 제외 {dup} · 합계 {len(out)}")
    print("분류:", cats.most_common())
    print("제외:", skipped.most_common(25))
    print("업종 대응:", subs.most_common(70))
    print("지역:", collections.Counter(p["area"] for p in out).most_common())
    print("합친 예:", [(p["name"], p.get("publicName")) for p in curated
                     if p["geo"] == "public" and norm(p["name"], strip) != norm(p.get("publicName", ""), strip)][:60])
    print("못 찾은 후보:", [p["name"] for p in curated if p["geo"] == "miss"][:60])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else download()
    with zipfile.ZipFile(path) as z:
        for region in REGIONS:
            merge_region(region, rows_of(z, region["member"]))


if __name__ == "__main__":
    main()
