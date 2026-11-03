# 점심 지도 (세종청사·여의도)

세종청사와 여의도에서 동료들이 다녀온 점심 식당을 함께 모으고 평가하는 지도 사이트예요.
맨 위에서 지역을 바꿀 수 있고, 식권 뽑기, 동네·종류·가격 필터, 기준점에서 가까운 순 정렬, 실제 지도(OpenStreetMap)를 지원해요.

지역별 바로가기: [세종청사](https://lloydknam.github.io/sejong-lunch/?r=sejong) · [여의도](https://lloydknam.github.io/sejong-lunch/?r=yeouido)

사이트 주소: https://lloydknam.github.io/sejong-lunch/

## 구조

| 파일 | 하는 일 |
|---|---|
| `index.html` | 사이트 전체 화면 |
| `data/places.json` | 세종 식당 목록 (맛집 후보 + 상가정보) |
| `data/yeouido.json` | 여의도 식당 목록 (맛집 후보 + 상가정보) |
| `config.js` | 구글 시트 저장소 주소, 카카오 JavaScript 키 |
| `scripts/import_public.py` | 공공데이터 상가정보를 받아 식당 목록에 합치는 스크립트 |
| `.github/workflows/import-public.yml` | 위 스크립트를 GitHub에서 실행 |
| `apps-script/Code.gs` | 구글 시트에 붙여넣는 저장소 코드 |

설정 전에는 사이트가 **내 폰에만 저장** 모드로 돌아가요. 아래 두 가지를 하면 완성이에요.

## 1. 구글 시트 연결 (등록·평가 공유)

1. 구글 드라이브에서 새 스프레드시트를 만들어요. 이름은 자유예요 (예: 세종청사 점심 저장소).
2. 메뉴 **확장 프로그램 → Apps Script**를 열어요.
3. 기본으로 있는 코드를 지우고 `apps-script/Code.gs` 내용을 통째로 붙여넣은 뒤 저장해요.
4. (선택) 왼쪽 톱니바퀴 **프로젝트 설정 → 스크립트 속성 → 속성 추가**
   - `PASSCODE` : 팀 암호. 넣으면 암호를 아는 사람만 등록·평가할 수 있어요. 사이트가 공개 주소라서 넣는 걸 권해요.
5. 오른쪽 위 **배포 → 새 배포 → 유형 선택(톱니) → 웹 앱**
   - 실행 사용자: **나**
   - 액세스 권한이 있는 사용자: **모든 사용자**
6. **배포**를 누르고 권한을 승인해요. "확인되지 않은 앱" 경고가 나오면 **고급 → (안전하지 않음)으로 이동**을 누르면 돼요. 내가 만든 스크립트라 괜찮아요.
7. 나오는 **웹 앱 URL**(`https://script.google.com/macros/s/.../exec`)을 `config.js`의 `sheetUrl`에 넣어요.

시트에 `places`, `reviews` 탭이 자동으로 생겨요. 잘못 올라온 항목은 시트에서 `deleted` 칸을 `TRUE`로 바꾸면 사이트에서 사라져요.

## 2. 카카오 JavaScript 키: 입구 로드뷰 (선택)

1. https://developers.kakao.com 의 앱에서 **JavaScript 키**를 확인해요.
2. 사이트 도메인에 `https://lloydknam.github.io` 를 등록해요.
3. 키를 `config.js`의 `kakaoJsKey`에 넣어요. 등록한 도메인에서만 작동해서 저장소에 넣어도 괜찮아요.

## 3. 식당 목록 갱신

식당 목록은 [소상공인시장진흥공단 상가(상권)정보](https://www.data.go.kr/data/15083033/fileData.do)에서 가져와요. 이용 제한이 없는 공공데이터이고 분기마다 갱신돼요.
**Actions → 공공데이터 식당 가져오기 → Run workflow**를 누르면 새 자료로 다시 합쳐요. 직접 모은 맛집 후보와 평가는 그대로 남아요.

카카오 로컬 API는 데이터를 저장하는 용도로 호출할 수 없어요. 그래서 검색 결과를 저장소에 넣지 않아요.

## 알아둘 점

- '맛집 후보'는 블로그·리뷰·당근 동네업체 정보로 모은 곳이라 폐업한 곳이 섞여 있을 수 있어요. 그 밖의 식당은 상가정보에 있는 곳이고, 맛을 검증한 목록은 아니에요.
- 세종의 상가정보는 신도심 동만 가져와요. 조치원읍과 면 지역은 맛집 후보로 넣은 곳만 있어요.
- 여의도 목록의 가격대는 출처에 나온 메뉴 가격 기준이에요. 위치를 못 찾은 '기타' 동네 식당은 지도에 안 나오고 목록에만 나와요.
- 새 지역을 넣으려면 `index.html`의 `REGIONS`, `apps-script/Code.gs`의 `REGIONS`, `scripts/geocode.py`의 `REGIONS`에 같이 추가해요.
- 직접 올린 식당과 평가만 직접 지울 수 있어요. 같은 폰·브라우저에서만 '내 것'으로 인식돼요.
- 지도 © OpenStreetMap 기여자

---

<a href="https://github.com/lloydknam"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/brand/lockup-dark.png"><img src="assets/brand/lockup-light.png" alt="Lloyd's Balcony Lab · with claude · GitHub(@lloydknam)" height="48"></picture></a>
