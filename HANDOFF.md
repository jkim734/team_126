# 배포 담당자 인수인계

먼저 `배포_안내.txt`를 화면 순서대로 따라 한 뒤 이 문서를 확인해 주세요.

## 최종 검수 상태 (2026-08-19)

- Python 3.13 로컬 실행 확인
- 공공데이터 인증키로 폐의약품·폐건전지/형광등·대형폐기물 API 연결 성공
- 5개 구·9개 동 일정 조회 확인
- 품목 검색과 미등록 품목 안내 확인
- 수거함 목록·다중 지도 마커·현재 위치 거리순 확인
- 현재 위치로 가장 가까운 지원 구·동 자동 선택 및 일정·기존 검색 결과 갱신 확인
- 대형폐기물 `매트리스 → 침대` 동의어 검색과 규격별 수수료 확인
- 데스크톱·모바일 반응형 화면 확인

인증키 실제 값은 전달 파일에 포함하지 않았습니다.

## 서비스 구성

- 웹 서버: `web_app.py` (Flask)
- 화면: `templates/index.html`, `static/app.js`, `static/style.css`
- 배포 의존성: `requirements-web.txt`
- Render 설정 예시: `render.yaml`

## 환경변수

배포 서비스의 **서버 환경변수**에 아래 값만 등록합니다.

- 이름: `DATA_GO_KR_API_KEY`
- 값: 공공데이터포털 일반 인증키(Decoding 또는 Encoding 키)

인증키를 Git 저장소, HTML, JavaScript, 공개 로그에 넣지 마세요. 앱은 서버의
환경변수에서만 키를 읽고 브라우저에는 결과 데이터만 보냅니다.

## 빌드·시작

- 빌드 명령: `pip install -r requirements-web.txt`
- 시작 명령: `gunicorn web_app:app`
- 권장 Python: 3.13 (검증 기준 3.13 계열)

현재 DB는 필요하지 않습니다. 회원가입·저장·수정 기능이 없고, 지역 일정과 공식
링크는 버전 관리되는 `waste_api.py`에 있으며 수거함·수수료는 요청 시 공식 API에서
읽기 때문입니다. 즐겨찾기, 사용자 제보, 운영자 수정 기능을 추가할 때 DB를 도입하면
됩니다.

## 배포 후 검증 URL

배포 주소가 `https://example.onrender.com`이라면 다음을 확인합니다.

1. `https://example.onrender.com/health` → `ok: true`
2. `https://example.onrender.com/api/regions` → 지원 구·동 목록
3. `https://example.onrender.com/api/schedule?district=성북구&dong=보문동` → 배출 일정
4. `https://example.onrender.com/api/search?q=우유팩&district=성북구` → 품목 안내
5. 메인 화면에서 위치 권한 허용 후 수거함이 가까운 순으로 표시되는지 확인
6. 대형폐기물 검색과 공식 신고 링크가 새 탭에서 열리는지 확인

위치 버튼은 별도 역지오코딩 서비스로 좌표를 전송하지 않습니다. 프론트에 저장된 9개
지원 동 기준점 중 5km 이내의 가장 가까운 곳을 자동 선택하고, 일정·기존 검색 결과·수거함을
한 번에 갱신합니다. 행정동 경계 인근에서는 사용자가 구·동 선택값을 직접 확인해야 합니다.

브라우저 현재 위치 기능은 공개 배포 주소가 HTTPS여야 정상적으로 권한을 요청할 수
있습니다. 배포 후 휴대폰과 PC 브라우저에서 각각 위치 권한을 허용해 재검수해 주세요.

## 배포 담당자가 반드시 할 일

1. 서버 환경변수 `DATA_GO_KR_API_KEY` 등록
2. `pip install -r requirements-web.txt` 실행
3. `gunicorn web_app:app`으로 시작
4. `/health`와 메인 화면 확인
5. HTTPS 공개 주소에서 위치 권한·수거함·수수료 재검수

회원가입·즐겨찾기·사용자 제보처럼 저장할 기능이 없으므로 현재 버전에는 DB가
필요하지 않습니다.

`/health`, `/api/regions`, `/api/schedule`, `/api/search`는 인증키 없이도 확인할 수
있습니다. 수거함과 수수료 API는 `DATA_GO_KR_API_KEY` 설정 후 점검합니다.
