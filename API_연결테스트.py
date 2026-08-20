"""공공데이터포털 인증키와 폐기물 API 3종의 연결 상태를 확인한다.

입력한 인증키는 화면에 표시되지 않으며 파일에 저장되지 않는다.
"""

from __future__ import annotations

import getpass

from waste_api import (
    BATTERY_LAMP_BOX_API,
    BULKY_WASTE_FEE_API,
    MEDICINE_BOX_API,
    PublicDataError,
    call_public_data_api,
    get_battery_lamp_boxes,
    get_bulky_waste_fees,
    get_medicine_boxes,
    get_supported_regions,
    get_waste_schedule,
    search_disposal_guide,
)


def test_connection(name: str, endpoint: str, api_key: str) -> bool:
    try:
        items = call_public_data_api(endpoint, api_key=api_key, rows=3)
        print(f"[연결 성공] {name}: 응답 {len(items)}건 확인")
        return True
    except (PublicDataError, ValueError) as exc:
        print(f"[연결 실패] {name}: {exc}")
        return False


def count_result(function) -> str:
    try:
        items = function()
        if not items:
            return "0건(공식 위치자료 미확보)"
        source = items[0].get("dataSource")
        if source == "official_csv_fallback":
            label = "성북구 공식 CSV"
        elif source == "smart_seoul_map_current_theme":
            label = "서울시 공식 스마트서울맵"
        elif source in {"official_static_fallback", "official_policy_fallback"}:
            label = "지자체 공식 안내"
        else:
            label = "표준 API"
        return f"{len(items)}건({label})"
    except (PublicDataError, ValueError) as exc:
        return f"조회 실패: {exc}"


def test_target_data(api_key: str) -> None:
    print("\n전체 대상 구 API 데이터 확인")
    print("지역 | 폐의약품 | 폐건전지·폐형광등 | 대형폐기물 수수료")
    print("-" * 76)
    for region in get_supported_regions():
        district = region["district"]
        medicine = count_result(lambda d=district: get_medicine_boxes(d, api_key))
        battery = count_result(lambda d=district: get_battery_lamp_boxes(d, api_key))
        bulky = count_result(lambda d=district: get_bulky_waste_fees(d, api_key=api_key))
        print(f"{district} | {medicine} | {battery} | {bulky}")

    print("\n내부 생활쓰레기 일정 확인")
    for region in get_supported_regions():
        district = region["district"]
        for dong_info in region["dongs"]:
            dong = dong_info["value"]
            result = get_waste_schedule(district, dong)
            print(f"- {district} {dong}: {result['status']}")


def test_old_sample(api_key: str) -> None:
    """필요할 때 개별 함수 응답을 빠르게 확인하기 위한 예시."""
    checks = (
        ("성북구 폐의약품 수거함", lambda: get_medicine_boxes("성북구", api_key)),
        ("성북구 폐건전지·폐형광등 수거함", lambda: get_battery_lamp_boxes("성북구", api_key)),
    )
    for name, function in checks:
        try:
            items = function()
            status = "데이터 있음" if items else "응답은 정상이나 데이터 없음"
            print(f"- {name}: {status} ({len(items)}건)")
        except (PublicDataError, ValueError) as exc:
            print(f"- {name}: 조회 실패 ({exc})")


def main() -> None:
    print("공공데이터 API 연결 테스트")
    print("인증키는 화면에 표시되거나 파일에 저장되지 않습니다.\n")
    for keyword in ("깨진 유리", "페트병", "매트리스", "폐의약품"):
        result = search_disposal_guide(keyword, "종로구")
        print(f"[품목 검색] {keyword}: {result['status']}")
    print()
    api_key = getpass.getpass("일반 인증키(Decoding)를 붙여넣고 Enter: ").strip()
    if not api_key:
        print("인증키가 입력되지 않았습니다.")
        return

    results = (
        test_connection("폐의약품 수거함", MEDICINE_BOX_API, api_key),
        test_connection("폐건전지·폐형광등 수거함", BATTERY_LAMP_BOX_API, api_key),
        test_connection("대형폐기물 수수료", BULKY_WASTE_FEE_API, api_key),
    )
    if all(results):
        print("\n세 API의 인증키 연결이 모두 정상입니다.")
        test_target_data(api_key)
    else:
        print("\n실패한 API의 활용신청 상태와 인증키 반영 여부를 확인해 주세요.")


if __name__ == "__main__":
    main()
