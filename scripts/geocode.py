"""data/places.json의 식당 위치를 카카오 로컬 API로 찾아 채웁니다.

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
PATH = os.path.join(os.path.dirname(__file__), "..", "data", "places.json")
FORCE = "--force" in sys.argv


def call(endpoint, params):
    url = f"https://dapi.kakao.com/v2/local/search/{endpoint}.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KEY}"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.load(res).get("documents", [])


def norm(s):
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(세종특별자치시|세종시|세종)", "", s)
    s = re.sub(r"[()&·+,.\-]", "", s)
    return s


def common_len(a, b):
    best = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a) + 1):
            if j - i > best and a[i:j] in b:
                best = j - i
    return best


def match(name, docs):
    n = norm(name)
    for d in docs:
        if not str(d.get("address_name", "")).startswith("세종"):
            continue
        c = norm(d.get("place_name", ""))
        need = min(3, len(n), len(c))
        if need and common_len(n, c) >= need:
            return d
    return None


def main():
    if not KEY:
        print("KAKAO_REST_KEY가 없어서 건너뜁니다.")
        return
    places = json.load(open(PATH, encoding="utf-8"))
    changed = 0
    for p in places:
        if p.get("geo") and not FORCE:
            continue
        try:
            docs = call("keyword", {"query": "세종 " + p["name"], "x": "127.26", "y": "36.50",
                                    "radius": "20000", "category_group_code": "FD6", "size": "5"})
            d = match(p["name"], docs)
            if d:
                p.update(lat=float(d["y"]), lng=float(d["x"]), kakaoUrl=d.get("place_url", ""),
                         kakaoAddr=d.get("road_address_name") or d.get("address_name", ""), geo="ok")
            elif p.get("address"):
                addr = p["address"]
                if not addr.startswith("세종"):
                    addr = "세종특별자치시 " + addr
                a = call("address", {"query": addr})
                if a:
                    p.update(lat=float(a[0]["y"]), lng=float(a[0]["x"]), geo="addr")
                else:
                    p["geo"] = "miss"
            else:
                p["geo"] = "miss"
            changed += 1
        except Exception as e:  # 네트워크 오류는 다음 실행에서 다시 시도
            print("오류:", p["name"], e)
        time.sleep(0.15)
    json.dump(places, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    counts = {}
    for p in places:
        counts[p.get("geo", "-")] = counts.get(p.get("geo", "-"), 0) + 1
    print(f"처리 {changed}곳 · 결과 {counts}")


if __name__ == "__main__":
    main()
