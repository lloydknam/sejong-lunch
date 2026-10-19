/**
 * 세종청사 점심 — 구글 시트 저장소
 *
 * 이 파일 전체를 구글 시트의 [확장 프로그램 → Apps Script]에 붙여넣고
 * [배포 → 새 배포 → 웹 앱]으로 배포하세요. 자세한 순서는 README.md에 있어요.
 *
 * 스크립트 속성(선택, [프로젝트 설정 → 스크립트 속성]):
 *   PASSCODE    : 팀 암호. 설정하면 암호를 아는 사람만 등록·평가할 수 있어요.
 *   KAKAO_KEY   : 카카오 REST API 키. 설정하면 새로 등록한 식당의 위치를 자동으로 찾아요.
 */

const PLACE_H = ['id','name','area','category','price','address','solo','group','reserve','note','nick','owner','createdAt','lat','lng','kakaoUrl','deleted'];
const REVIEW_H = ['id','placeId','verdict','text','nick','owner','createdAt','deleted'];
const AREAS = ['어진동','나성동','도담동','보람동','아름동','종촌동','고운동','새롬동','다정동','한솔동','대평동','소담동','반곡동','집현동','조치원읍','금남면','장군면','기타'];
const CATS = ['한식','일식','중식','양식','아시아','분식','고기','해산물','카페·빵','기타'];
const PRICES = ['','~1만','1~1.5만','1.5만~'];
const VERDICTS = ['again','ok','no'];

function sheet_(name, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); sh.appendRow(headers); sh.setFrozenRows(1); }
  return sh;
}

function rows_(name, headers) {
  const values = sheet_(name, headers).getDataRange().getValues();
  values.shift();
  return values.map(r => {
    const o = {};
    headers.forEach((h, i) => { o[h] = r[i]; });
    return o;
  });
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function hash_(token) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(token), Utilities.Charset.UTF_8);
  return bytes.map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('').slice(0, 16);
}

function str_(v, max) { return String(v == null ? '' : v).trim().slice(0, max); }
function bool_(v) { return v === true || v === 'TRUE' || v === 'true'; }

function doGet() {
  const places = rows_('places', PLACE_H).filter(p => p.id && !bool_(p.deleted)).map(p => ({
    id: String(p.id), name: p.name, area: p.area, category: p.category, price: p.price, address: p.address,
    solo: bool_(p.solo), group: bool_(p.group), reserve: bool_(p.reserve), note: p.note, nick: p.nick,
    owner: p.owner, createdAt: Number(p.createdAt) || 0,
    lat: p.lat === '' ? null : Number(p.lat), lng: p.lng === '' ? null : Number(p.lng), kakaoUrl: p.kakaoUrl || ''
  }));
  const reviews = rows_('reviews', REVIEW_H).filter(r => r.id && !bool_(r.deleted)).map(r => ({
    id: String(r.id), placeId: String(r.placeId), verdict: r.verdict, text: r.text, nick: r.nick,
    owner: r.owner, createdAt: Number(r.createdAt) || 0
  }));
  return json_({ ok: true, places: places, reviews: reviews, needsPasscode: !!PropertiesService.getScriptProperties().getProperty('PASSCODE') });
}

function doPost(e) {
  let body;
  try { body = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'bad_request' }); }

  const props = PropertiesService.getScriptProperties();
  const pass = props.getProperty('PASSCODE');
  if (pass && body.passcode !== pass) return json_({ ok: false, error: 'passcode' });
  if (!body.token || String(body.token).length < 16) return json_({ ok: false, error: 'bad_request' });
  const owner = hash_(body.token);

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (body.action === 'addPlace') return addPlace_(body, owner, props);
    if (body.action === 'addReview') return addReview_(body, owner);
    if (body.action === 'deletePlace') return softDelete_('places', PLACE_H, body.id, owner);
    if (body.action === 'deleteReview') return softDelete_('reviews', REVIEW_H, body.id, owner);
    return json_({ ok: false, error: 'bad_request' });
  } finally {
    lock.releaseLock();
  }
}

function addPlace_(b, owner, props) {
  const name = str_(b.name, 40);
  if (!name) return json_({ ok: false, error: 'bad_request' });
  const existing = rows_('places', PLACE_H).filter(p => !bool_(p.deleted));
  const key = name.replace(/\s/g, '');
  if (existing.some(p => String(p.name).replace(/\s/g, '') === key)) return json_({ ok: false, error: 'duplicate' });

  const area = AREAS.indexOf(b.area) >= 0 ? b.area : '기타';
  const category = CATS.indexOf(b.category) >= 0 ? b.category : '기타';
  const price = PRICES.indexOf(b.price) >= 0 ? b.price : '';
  const address = str_(b.address, 60);
  let lat = '', lng = '', kakaoUrl = '';
  const kakao = props.getProperty('KAKAO_KEY');
  if (kakao) {
    const hit = kakaoLookup_(kakao, name);
    if (hit) { lat = hit.lat; lng = hit.lng; kakaoUrl = hit.url; }
  }
  const id = 'u-' + Utilities.getUuid().slice(0, 12);
  sheet_('places', PLACE_H).appendRow([
    id, name, area, category, price, address, !!b.solo, !!b.group, !!b.reserve, str_(b.note, 60),
    str_(b.nick, 20), owner, Date.now(), lat, lng, kakaoUrl, false
  ]);
  return json_({ ok: true, id: id });
}

function addReview_(b, owner) {
  const placeId = str_(b.placeId, 40);
  const verdict = VERDICTS.indexOf(b.verdict) >= 0 ? b.verdict : 'ok';
  if (!placeId) return json_({ ok: false, error: 'bad_request' });
  const id = 'r-' + Utilities.getUuid().slice(0, 12);
  sheet_('reviews', REVIEW_H).appendRow([id, placeId, verdict, str_(b.text, 80), str_(b.nick, 20), owner, Date.now(), false]);
  return json_({ ok: true, id: id });
}

function softDelete_(name, headers, id, owner) {
  const sh = sheet_(name, headers);
  const values = sh.getDataRange().getValues();
  const idCol = headers.indexOf('id'), ownerCol = headers.indexOf('owner'), delCol = headers.indexOf('deleted');
  for (let i = 1; i < values.length; i++) {
    if (String(values[i][idCol]) === String(id)) {
      if (values[i][ownerCol] !== owner) return json_({ ok: false, error: 'not_owner' });
      sh.getRange(i + 1, delCol + 1).setValue(true);
      return json_({ ok: true });
    }
  }
  return json_({ ok: false, error: 'not_found' });
}

function kakaoLookup_(key, name) {
  const url = 'https://dapi.kakao.com/v2/local/search/keyword.json?query=' + encodeURIComponent('세종 ' + name) +
    '&x=127.26&y=36.50&radius=20000&category_group_code=FD6&size=5';
  const res = UrlFetchApp.fetch(url, { headers: { Authorization: 'KakaoAK ' + key }, muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return null;
  const docs = JSON.parse(res.getContentText()).documents || [];
  const doc = docs.find(d => String(d.address_name).indexOf('세종') === 0);
  return doc ? { lat: Number(doc.y), lng: Number(doc.x), url: doc.place_url } : null;
}
