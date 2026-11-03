"""지역별 식당 목록(data/places.json, data/yeouido.json)의 위치를 카카오 로컬 API로 찾아 채웁니다.

GitHub Actions에서 KAKAO_REST_KEY 비밀값으로 실행돼요. 직접 돌릴 때는:
    KAKAO_REST_KEY=... python scripts/geocode.py

geo 값:
  ok   카카오맵에서 같은 식당을 찾음 (lat, lng, kakaoUrl 채움)
  addr 식당은 못 찾았지만 주소로 위치를 찾음
  miss 둘 다 못 찾음 (지도에는 동 중심 근처에 대략 표시)
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

KEY = os.environ.get("KAKAO_REST_KEY", "").strip()
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
REGIONS = [
    {"file": "places.json", "query": "세종 ", "x": "127.26", "y": "36.50", "radius": "20000",
     "addr_has": "세종", "addr_prefix": "세종특별자치시 ", "addr_skip": "세종", "strip": r"(세종특별자치시|세종시|세종)"},
    {"file": "yeouido.json", "query": "여의도 ", "x": "126.925", "y": "37.525", "radius": "3000",
     "addr_has": "여의도동", "addr_prefix": "서울 영등포구 ", "addr_skip": "서울", "strip": r"(여의도)",
     # 위치를 찾으면 가장 가까운 구역으로 정리해요. index.html의 center와 같은 값이에요.
     "centers": {"국회·서여의도": (37.5272, 126.9192), "여의도역·IFC": (37.5235, 126.9250), "증권가": (37.5222, 126.9285),
                 "여의나루": (37.5262, 126.9322), "샛강·63": (37.5180, 126.9315)}},
]
FORCE = "--force" in sys.argv


def call(endpoint, params):
    url = f"https://dapi.kakao.com/v2/local/search/{endpoint}.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KEY}"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.load(res).get("documents", [])


def norm(s, strip):
    s = re.sub(r"\s+", "", s)
    s = re.sub(strip, "", s)
    s = re.sub(r"[()&·+,.\-]", "", s)
    return s


def common_len(a, b):
    best = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a) + 1):
            if j - i > best and a[i:j] in b:
                best = j - i
    return best


def road_key(address):
    """주소에서 '국제금융로6길 33' 같은 도로명+번호를 뽑습니다."""
    m = re.search(r"([가-힣0-9]+(?:대로|로|길))\s+([0-9]+(?:-[0-9]+)?)(?![0-9]*(?:층|호))", address or "")
    return f"{m.group(1)} {m.group(2)}" if m else None


def match(place, docs, region):
    """같은 식당인 카카오 장소를 고릅니다. 확신이 없으면 None을 돌려줘 주소로 찾게 합니다.

    1) 이름이 비슷하고 주소도 같은 곳  2) 이름이 정확히 같은 곳
    3) 우리 쪽 주소가 없을 때만, 이름의 대부분이 겹치는 곳
    """
    n = norm(place["name"], region["strip"])
    key = road_key(place.get("address"))
    similar, exact = [], []
    for d in docs:
        if region["addr_has"] not in str(d.get("address_name", "")):
            continue
        c = norm(d.get("place_name", ""), region["strip"])
        if not n or not c:
            continue
        if n == c:
            exact.append(d)
        elif min(len(n), len(c)) >= 3 and common_len(n, c) >= max(3, round(len(n) * 0.6)):
            similar.append(d)
    if key:
        for d in exact + similar:
            if key in str(d.get("road_address_name", "")) or key in str(d.get("address_name", "")):
                return d
    if exact:
        return exact[0]
    if similar and not key:
        return similar[0]
    return None


def nearest_area(lat, lng, centers):
    return min(centers, key=lambda a: (centers[a][0] - lat) ** 2 + (centers[a][1] - lng) ** 2)


def geocode_region(region):
    path = os.path.join(DATA, region["file"])
    places = json.load(open(path, encoding="utf-8"))
    changed = 0
    for p in places:
        if p.get("geo") and not FORCE:
            continue
        try:
            docs = call("keyword", {"query": region["query"] + p["name"], "x": region["x"], "y": region["y"],
                                    "radius": region["radius"], "category_group_code": "FD6", "size": "5"})
            d = match(p, docs, region)
            if d:
                p.update(lat=float(d["y"]), lng=float(d["x"]), kakaoUrl=d.get("place_url", ""),
                         kakaoAddr=d.get("road_address_name") or d.get("address_name", ""),
                         kakaoName=d.get("place_name", ""), geo="ok")
            elif p.get("address"):
                addr = p["address"]
                if not addr.startswith(region["addr_skip"]):
                    addr = region["addr_prefix"] + addr
                a = call("address", {"query": addr})
                if a:
                    p.update(lat=float(a[0]["y"]), lng=float(a[0]["x"]), geo="addr")
                else:
                    p["geo"] = "miss"
            else:
                p["geo"] = "miss"
            if region.get("centers") and isinstance(p.get("lat"), float):
                p["area"] = nearest_area(p["lat"], p["lng"], region["centers"])
            changed += 1
        except Exception as e:  # 네트워크 오류는 다음 실행에서 다시 시도
            print("오류:", p["name"], e)
        time.sleep(0.15)
    json.dump(places, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    counts = {}
    for p in places:
        counts[p.get("geo", "-")] = counts.get(p.get("geo", "-"), 0) + 1
    print(f"{region['file']}: 처리 {changed}곳 · 결과 {counts}")


def main():
    if not KEY:
        print("KAKAO_REST_KEY가 없어서 건너뜁니다.")
        return
    for region in REGIONS:
        geocode_region(region)


if __name__ == "__main__":
    main()
