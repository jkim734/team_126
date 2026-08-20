"""성균관대 주요 자취 생활권용 폐기물 정보 함수 모음.

공공데이터포털의 일반 인증키(Decoding key)를 ``DATA_GO_KR_API_KEY``
환경변수에 저장한 뒤 사용한다. 외부 패키지 없이 Python 표준 라이브러리만
사용하도록 작성했다.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen


MEDICINE_BOX_API = (
    "https://api.data.go.kr/openapi/tn_pubr_public_lung_medicine_api"
)
BATTERY_LAMP_BOX_API = (
    "https://api.data.go.kr/openapi/"
    "tn_pubr_public_waste_lamp_battery_collection_box_api"
)
BULKY_WASTE_FEE_API = (
    "https://api.data.go.kr/openapi/tn_pubr_public_lar_was_fee_api"
)

SEONGBUK_BATTERY_LAMP_CSV = (
    "https://www.data.go.kr/cmm/cmm/fileDownload.do?"
    "atchFileId=FILE_000000001553368&fileDetailSn=1&insertDataPrcus=N"
)


# 생활권은 사용자에게 보여줄 이름이고, 시군구는 공공 API 조회에 사용한다.
AREA_PROFILES: dict[str, dict[str, Any]] = {
    "혜화·명륜": {
        "aliases": ("혜화", "명륜", "명륜동", "혜화동"),
        "sido": "서울특별시",
        "sigungu": "종로구",
        "admin_dongs": ("혜화동",),
    },
    "한성대입구": {
        "aliases": ("한성대", "한성대역", "한성대입구역", "삼선동"),
        "sido": "서울특별시",
        "sigungu": "성북구",
        "admin_dongs": ("삼선동", "성북동"),
        "notice": "역 양쪽의 행정동이 달라 실제 주소 확인이 필요합니다.",
    },
    "성신여대입구": {
        "aliases": ("성신여대", "성신여대역", "성신여대입구역", "동선동"),
        "sido": "서울특별시",
        "sigungu": "성북구",
        "admin_dongs": ("동선동",),
        "notice": "동선동 일부 구역은 배출 요일이 달라 실제 주소 확인이 필요합니다.",
    },
    "보문": {
        "aliases": ("보문역", "보문동"),
        "sido": "서울특별시",
        "sigungu": "성북구",
        "admin_dongs": ("보문동",),
    },
    "율전·천천": {
        "aliases": ("율전", "율전동", "천천", "천천동", "율천동"),
        "sido": "경기도",
        "sigungu": "수원시",
        "gu": "장안구",
        "admin_dongs": ("율천동",),
    },
    "화서": {
        "aliases": ("화서동", "화서1동", "화서2동"),
        "sido": "경기도",
        "sigungu": "수원시",
        "gu": "팔달구",
        "admin_dongs": ("화서1동", "화서2동"),
    },
    "구운": {
        "aliases": ("구운동",),
        "sido": "경기도",
        "sigungu": "수원시",
        "gu": "권선구",
        "admin_dongs": ("구운동",),
    },
}


# 웹 화면에서 직접 선택하는 5개 구. 수원의 3개 구는 공공데이터 API에서
# 시군구명이 '수원시'로 제공될 수 있어 api_sigungu와 화면 이름을 분리한다.
DISTRICT_PROFILES: dict[str, dict[str, Any]] = {
    "종로구": {
        "sido": "서울특별시",
        "api_sigungu": "종로구",
        "dongs": ("혜화동",),
        "labels": {"혜화동": "혜화동·명륜동"},
    },
    "성북구": {
        "sido": "서울특별시",
        "api_sigungu": "성북구",
        "dongs": ("삼선동", "성북동", "동선동", "보문동"),
    },
    "장안구": {
        "sido": "경기도",
        "api_sigungu": "수원시",
        "address_filter": "장안구",
        "dongs": ("율천동",),
        "labels": {"율천동": "율천동(율전·천천)"},
    },
    "팔달구": {
        "sido": "경기도",
        "api_sigungu": "수원시",
        "address_filter": "팔달구",
        "dongs": ("화서1동", "화서2동"),
    },
    "권선구": {
        "sido": "경기도",
        "api_sigungu": "수원시",
        "address_filter": "권선구",
        "dongs": ("구운동",),
    },
}

DONG_ALIASES = {
    "혜화": "혜화동",
    "명륜": "혜화동",
    "명륜동": "혜화동",
    "삼선": "삼선동",
    "성북": "성북동",
    "동선": "동선동",
    "보문": "보문동",
    "율전": "율천동",
    "율전동": "율천동",
    "천천": "율천동",
    "천천동": "율천동",
    "화서1": "화서1동",
    "화서2": "화서2동",
    "구운": "구운동",
}


SEONGBUK_SOURCE = (
    "https://www.sb.go.kr/www/selectBbsNttView.do?"
    "bbsNo=91&key=5927&nttNo=9502164"
)
SUWON_SOURCE = (
    "https://www.suwon.go.kr/webcontent/ckeditor/2026/4/21/"
    "c7591f6e-26c9-40fd-83c4-071a976041cf.pdf"
)
SEOUL_MEDICINE_SOURCE = "https://news.seoul.go.kr/env/archives/563744"
SEONGBUK_BOX_SOURCE = "https://www.data.go.kr/data/15038083/fileData.do"
SUWON_BOX_SOURCE = (
    "https://www.suwon.go.kr/sw-www/deptHome/dep_env/env_03/env_03_09.jsp"
)
JONGNO_BOX_STATUS_SOURCE = (
    "https://bookcouncil.jongno.go.kr/attach/record/JONGNO/appendix/a09/A0012024.pdf"
)
SMART_SEOUL_MAP_API = "https://map.seoul.go.kr/smgis2/qry/THEME"
SMART_SEOUL_MAP_GUIDE = "https://map.seoul.go.kr/smgis2/division/viewOpenApi"
JONGNO_WASTE_DAYS_SOURCE = "https://blog.naver.com/jongno0401/223323129613"
SMART_SEOUL_BATTERY_LAMP_THEME_ID = "11103389"
SMART_SEOUL_MEDICINE_THEME_ID = "1649132420936"


# 표준 API에 자료가 없는 지역을 위한 공식 확인 거점이다. 수원시는 공식 안내에서
# 각 동 행정복지센터를 폐건전지·폐형광등 수거 장소로 안내한다.
STATIC_BATTERY_LAMP_BOXES: dict[str, list[dict[str, Any]]] = {
    "장안구": [
        {
            "clctKndNm": "폐건전지·폐형광등",
            "lctnRoadNm": "경기도 수원시 장안구 서부로2106번길 27",
            "placeName": "율천동 행정복지센터",
            "adminDong": "율천동",
            "lat": 37.2976195,
            "lot": 126.9714636,
            "source": SUWON_BOX_SOURCE,
            "dataSource": "official_static_fallback",
            "verified": True,
        }
    ],
    "팔달구": [
        {
            "clctKndNm": "폐건전지·폐형광등",
            "lctnRoadNm": "경기도 수원시 팔달구 동말로4번길 10",
            "placeName": "화서1동 행정복지센터",
            "adminDong": "화서1동",
            "lat": 37.2764022,
            "lot": 126.9950268,
            "source": SUWON_BOX_SOURCE,
            "dataSource": "official_static_fallback",
            "verified": True,
        },
        {
            "clctKndNm": "폐건전지·폐형광등",
            "lctnRoadNm": "경기도 수원시 팔달구 화산로6번길 6",
            "placeName": "화서2동 행정복지센터",
            "adminDong": "화서2동",
            "lat": 37.2850707,
            "lot": 126.9863215,
            "source": SUWON_BOX_SOURCE,
            "dataSource": "official_static_fallback",
            "verified": True,
        },
    ],
    "권선구": [
        {
            "clctKndNm": "폐건전지·폐형광등",
            "lctnRoadNm": "경기도 수원시 권선구 구운로47번길 57-33",
            "placeName": "구운동 행정복지센터",
            "adminDong": "구운동",
            "lat": 37.2771517,
            "lot": 126.9714384,
            "source": SUWON_BOX_SOURCE,
            "dataSource": "official_static_fallback",
            "verified": True,
        }
    ],
}


# 통합 API가 없는 정보이므로 공식 안내를 검증해 앱 내부 데이터로 보관한다.
WASTE_SCHEDULES: dict[str, dict[str, Any]] = {
    "혜화동": {
        "general_food": {
            "days": ("일", "월", "화", "수", "목", "금"),
            "time": "온라인 공식 자료에서 정확한 시간 미확인",
        },
        "recycle": {
            "days": ("일", "월", "화", "수", "목", "금"),
            "time": "온라인 공식 자료에서 정확한 시간 미확인",
        },
        "notice": (
            "혜화동·명륜1~4가는 2024년부터 일반·음식물·재활용을 매일 "
            "배출할 수 있으며 토요일은 배출하지 않습니다. 배출 마감시간은 "
            "온라인 공식 자료만으로 확정하지 않았습니다."
        ),
        "source": JONGNO_WASTE_DAYS_SOURCE,
        "verified": True,
        "timeVerified": False,
    },
    "삼선동": {
        "general_food": {"days": ("화", "목", "일"), "time": "18:00~20:00"},
        "recycle": {"days": ("화", "목", "일"), "time": "18:00~20:00"},
        "source": SEONGBUK_SOURCE,
        "verified": True,
    },
    "성북동": {
        "general_food": {"days": ("월", "수", "금"), "time": "18:00~20:00"},
        "recycle": {"days": ("월", "수", "금"), "time": "18:00~20:00"},
        "notice": "성북동1가는 화·목·일 배출이므로 상세 주소 확인이 필요합니다.",
        "source": SEONGBUK_SOURCE,
        "verified": True,
    },
    "동선동": {
        "general_food": {"days": ("화", "목", "일"), "time": "18:00~20:00"},
        "recycle": {"days": ("일", "월", "화", "수", "목", "금"), "time": "18:00~20:00"},
        "notice": "동선동4·5가와 동소문동6·7가는 일반·음식물이 월·수·금입니다.",
        "source": SEONGBUK_SOURCE,
        "verified": True,
    },
    "보문동": {
        "general_food": {"days": ("월", "수", "금"), "time": "18:00~20:00"},
        "recycle": {"days": ("월", "수", "금"), "time": "18:00~20:00"},
        "source": SEONGBUK_SOURCE,
        "verified": True,
    },
    "율천동": {
        "all_waste": {"days": ("일", "월", "화", "수", "목"), "time": "20:00~05:00"},
        "notice": "공동주택은 자체 지정 장소·시간을 따르며 품목별 수거일은 달라질 수 있습니다.",
        "source": SUWON_SOURCE,
        "verified": True,
    },
    "화서1동": {
        "all_waste": {"days": ("일", "월", "화", "수", "목"), "time": "20:00~05:00"},
        "notice": "공동주택은 자체 지정 장소·시간을 따르며 품목별 수거일은 달라질 수 있습니다.",
        "source": SUWON_SOURCE,
        "verified": True,
    },
    "화서2동": {
        "all_waste": {"days": ("일", "월", "화", "수", "목"), "time": "20:00~05:00"},
        "notice": "공동주택은 자체 지정 장소·시간을 따르며 품목별 수거일은 달라질 수 있습니다.",
        "source": SUWON_SOURCE,
        "verified": True,
    },
    "구운동": {
        "all_waste": {"days": ("일", "월", "화", "수", "목"), "time": "20:00~05:00"},
        "notice": "공동주택은 자체 지정 장소·시간을 따르며 품목별 수거일은 달라질 수 있습니다.",
        "source": SUWON_SOURCE,
        "verified": True,
    },
}


SEOUL_DISPOSAL_GUIDE_SOURCE = "https://news.seoul.go.kr/env/archives/564022"
MINISTRY_RECYCLING_SOURCE = (
    "https://me.go.kr/home/web/board/read.do?boardId=1398800&boardMasterId=54"
)


# 사진 인식 없이 품목명을 검색하는 기능에 사용한다. 지자체마다 봉투·수거 방식이
# 달라질 수 있는 항목은 주의 문구와 해당 지역 공식 신고 페이지를 함께 반환한다.
DISPOSAL_GUIDES: tuple[dict[str, Any], ...] = (
    {
        "item": "투명 페트병",
        "aliases": ("생수병", "음료 페트병", "페트병", "PET병"),
        "category": "투명 페트병",
        "method": "내용물을 비우고 헹군 뒤 라벨을 떼고 찌그러뜨려 뚜껑을 닫아 별도 배출합니다.",
        "caution": "유색 페트병과 다른 플라스틱 용기는 플라스틱류로 분리합니다.",
        "bulky": False,
    },
    {
        "item": "플라스틱 용기",
        "aliases": ("배달용기", "반찬통", "샴푸통", "세제통", "유색 페트병"),
        "category": "플라스틱류",
        "method": "내용물을 비우고 깨끗이 헹군 뒤 라벨·뚜껑 등 다른 재질을 분리해 배출합니다.",
        "caution": "씻어도 음식물이나 기름이 제거되지 않으면 종량제봉투에 버립니다.",
        "bulky": False,
    },
    {
        "item": "스티로폼",
        "aliases": ("스티로폼 상자", "완충재", "과일 포장망"),
        "category": "발포합성수지",
        "method": "내용물을 비우고 테이프·송장·상표를 제거한 깨끗한 흰색 스티로폼만 분리배출합니다.",
        "caution": "색깔·무늬가 있거나 오염된 스티로폼과 과일 포장망은 종량제봉투 대상입니다.",
        "bulky": False,
    },
    {
        "item": "비닐",
        "aliases": ("과자봉지", "커피봉지", "택배봉투", "뽁뽁이", "에어캡", "양파망"),
        "category": "비닐류",
        "method": "내용물을 비우고 이물질을 제거한 뒤 투명 봉투에 모아 배출합니다.",
        "caution": "랩·은박비닐처럼 재활용이 어려운 재질은 종량제봉투에 버립니다.",
        "bulky": False,
    },
    {
        "item": "컵라면 용기",
        "aliases": ("라면 용기", "라면컵"),
        "category": "용기 재질에 따라 분류",
        "method": "표시된 재질을 확인하고 깨끗이 씻어 종이 또는 플라스틱·스티로폼류로 배출합니다.",
        "caution": "국물 자국과 기름기가 제거되지 않으면 종량제봉투에 버립니다.",
        "bulky": False,
    },
    {
        "item": "택배 상자",
        "aliases": ("종이 상자", "골판지", "박스"),
        "category": "종이류",
        "method": "송장·테이프·철핀 등 다른 재질을 제거하고 펼쳐서 묶어 배출합니다.",
        "caution": "비닐이나 알루미늄이 붙어 분리되지 않는 보냉 상자는 종량제봉투 대상입니다.",
        "bulky": False,
    },
    {
        "item": "일반 종이",
        "aliases": ("신문", "책", "노트", "전단지"),
        "category": "종이류",
        "method": "물기에 젖지 않게 하고 스프링·비닐 등 다른 재질을 제거한 뒤 묶어 배출합니다.",
        "caution": "영수증·코팅지·사진·종이호일·사용한 휴지는 종량제봉투에 버립니다.",
        "bulky": False,
    },
    {
        "item": "영수증",
        "aliases": ("감열지", "택배 전표", "사진", "종이호일"),
        "category": "일반쓰레기",
        "method": "종량제봉투에 버립니다.",
        "caution": "종이처럼 보여도 재활용 종이류에 섞지 않습니다.",
        "bulky": False,
    },
    {
        "item": "종이팩",
        "aliases": ("우유팩", "주스팩", "멸균팩"),
        "category": "종이팩류",
        "method": "내용물을 비우고 헹군 뒤 펼쳐 말려 종이팩 전용 수거함에 배출합니다.",
        "caution": "일반 종이와 분리하며 전용 수거함이 없다면 지자체 안내를 확인합니다.",
        "bulky": False,
    },
    {
        "item": "유리병",
        "aliases": ("소주병", "맥주병", "음료수병", "잼병"),
        "category": "유리병류",
        "method": "내용물을 비우고 헹군 뒤 뚜껑 등 다른 재질을 제거해 깨지지 않게 배출합니다.",
        "caution": "빈용기보증금 대상 병은 소매점에 반환할 수 있습니다.",
        "bulky": False,
    },
    {
        "item": "깨진 유리",
        "aliases": ("유리 조각", "깨진 컵", "깨진 병"),
        "category": "일반 또는 불연성 폐기물",
        "method": "소량은 신문지 등에 안전하게 싸서 종량제봉투에, 다량은 지역 특수규격마대에 배출합니다.",
        "caution": "겉면에 깨진 유리임을 표시하고 지자체별 특수마대 기준을 확인합니다.",
        "bulky": False,
    },
    {
        "item": "도자기",
        "aliases": ("사기그릇", "화분", "내열유리", "거울", "판유리"),
        "category": "불연성 또는 대형폐기물",
        "method": "지역 특수규격마대 또는 대형폐기물 신고 방식으로 배출합니다.",
        "caution": "유리병 수거함에 넣지 말고 깨진 부분을 안전하게 포장합니다.",
        "bulky": "depends_on_size",
    },
    {
        "item": "금속 캔",
        "aliases": ("음료수 캔", "맥주 캔", "통조림 캔"),
        "category": "금속캔류",
        "method": "내용물을 비우고 헹군 뒤 플라스틱 뚜껑 등 다른 재질을 제거해 배출합니다.",
        "caution": "담배꽁초 등 이물질을 넣지 않습니다.",
        "bulky": False,
    },
    {
        "item": "부탄가스·스프레이",
        "aliases": ("부탄가스", "가스통", "스프레이", "살충제", "에어로졸"),
        "category": "기타 캔류",
        "method": "불꽃이 없고 통풍이 잘되는 곳에서 내용물을 완전히 제거한 뒤 지역 캔류 배출 기준에 따릅니다.",
        "caution": "내용물이 남은 용기는 폭발 위험이 있으므로 임의로 배출하지 말고 지자체 안내를 확인합니다.",
        "bulky": False,
    },
    {
        "item": "알루미늄 포일",
        "aliases": ("은박지", "쿠킹호일", "호일"),
        "category": "일반쓰레기",
        "method": "종량제봉투에 버립니다.",
        "caution": "금속캔류에 섞지 않습니다.",
        "bulky": False,
    },
    {
        "item": "폐건전지",
        "aliases": ("건전지", "보조배터리", "충전지", "배터리"),
        "category": "전지류",
        "method": "일반쓰레기나 캔류에 넣지 말고 폐건전지 전용 수거함에 배출합니다.",
        "caution": "리튬전지는 단자를 테이프로 감싸 절연하면 화재 예방에 도움이 됩니다.",
        "bulky": False,
        "relatedFunction": "find_nearest_collection_boxes(..., waste_type='폐건전지')",
    },
    {
        "item": "폐형광등",
        "aliases": ("형광등", "형광램프"),
        "category": "폐형광등",
        "method": "깨지지 않게 폐형광등 전용 수거함에 배출합니다.",
        "caution": "깨진 형광등은 안전하게 포장한 뒤 지역별 배출 기준을 확인합니다.",
        "bulky": False,
        "relatedFunction": "find_nearest_collection_boxes(..., waste_type='폐형광등')",
    },
    {
        "item": "폐의약품",
        "aliases": ("약", "알약", "가루약", "연고", "물약", "시럽"),
        "category": "폐의약품",
        "method": "포장재를 가능한 만큼 분리하고 폐의약품 전용 수거함에 배출합니다.",
        "caution": "물약·시럽은 우체통이 아닌 주민센터·보건소 등의 전용 수거함에 배출합니다.",
        "bulky": False,
        "relatedFunction": "find_nearest_collection_boxes(..., waste_type='폐의약품')",
    },
    {
        "item": "화장품 용기",
        "aliases": ("화장품", "로션통", "향수병"),
        "category": "용기 재질에 따라 분류",
        "method": "내용물을 제거하고 펌프·스프링 등 다른 재질을 분리한 뒤 용기 재질에 맞게 배출합니다.",
        "caution": "내용물과 복합재질을 제거하기 어렵다면 종량제봉투에 버립니다.",
        "bulky": False,
    },
    {
        "item": "아이스팩",
        "aliases": ("젤 아이스팩", "물 아이스팩"),
        "category": "재질에 따라 분류",
        "method": "물로 된 제품은 물을 버리고 포장재를 재질별 배출하며, 젤형은 통째로 종량제봉투에 버립니다.",
        "caution": "젤 내용물을 하수구에 흘려보내지 않습니다.",
        "bulky": False,
    },
    {
        "item": "칫솔",
        "aliases": ("볼펜", "CD", "DVD", "플라스틱 옷걸이"),
        "category": "일반쓰레기",
        "method": "종량제봉투에 버립니다.",
        "caution": "플라스틱처럼 보여도 여러 재질이 섞인 생활용품은 재활용하기 어렵습니다.",
        "bulky": False,
    },
    {
        "item": "플라스틱 장난감",
        "aliases": ("장난감", "완구"),
        "category": "일반 또는 전자폐기물",
        "method": "배터리가 없는 소형 혼합재질 완구는 종량제봉투에, 배터리·회로가 있는 제품은 소형 폐가전 수거함에 배출합니다.",
        "caution": "크기가 커서 종량제봉투에 들어가지 않으면 대형폐기물로 신고합니다.",
        "bulky": "depends_on_size",
    },
    {
        "item": "소형 폐가전",
        "aliases": ("드라이기", "전기밥솥", "선풍기", "다리미", "휴대폰", "노트북"),
        "category": "폐전기·전자제품",
        "method": "소형 폐가전 전용 수거함 또는 지자체가 안내하는 무상수거 방식으로 배출합니다.",
        "caution": "분리 가능한 배터리는 제거해 폐건전지 수거함에 따로 배출합니다.",
        "bulky": False,
    },
    {
        "item": "대형 폐가전",
        "aliases": ("냉장고", "세탁기", "에어컨", "텔레비전", "TV"),
        "category": "대형 폐가전",
        "method": "폐가전 무상방문수거 대상 여부를 확인해 예약 배출합니다.",
        "caution": "제품을 훼손하거나 부품을 떼면 무상수거가 거절될 수 있습니다.",
        "bulky": True,
    },
    {
        "item": "의류",
        "aliases": ("옷", "가방", "신발"),
        "category": "폐의류",
        "method": "깨끗하고 재사용 가능한 것은 의류수거함에 배출합니다.",
        "caution": "젖거나 심하게 오염된 의류와 솜이불 등은 지역 종량제·대형폐기물 기준을 따릅니다.",
        "bulky": False,
    },
    {
        "item": "이불",
        "aliases": ("솜이불", "베개", "쿠션"),
        "category": "대형 또는 종량제 폐기물",
        "method": "지역에 따라 대형폐기물 신고 또는 종량제봉투 방식이 다르므로 공식 신고 페이지에서 확인합니다.",
        "caution": "의류수거함에 넣지 않습니다.",
        "bulky": "local_rule",
    },
    {
        "item": "프라이팬",
        "aliases": ("냄비", "고철", "철제 조리도구"),
        "category": "고철류",
        "method": "음식물과 기름을 제거하고 분리 가능한 플라스틱 손잡이 등은 떼어 고철류로 배출합니다.",
        "caution": "분리가 어렵거나 지역 고철 수거 기준에 맞지 않으면 지자체 안내를 확인합니다.",
        "bulky": False,
    },
    {
        "item": "우산",
        "aliases": ("양산",),
        "category": "혼합재질 폐기물",
        "method": "가능하면 천과 금속대를 분리해 각각 종량제봉투와 고철류로 배출합니다.",
        "caution": "분리하기 어렵거나 봉투에 들어가지 않으면 지역 대형폐기물 기준을 확인합니다.",
        "bulky": "depends_on_size",
    },
    {
        "item": "가구",
        "aliases": ("의자", "책상", "침대", "매트리스", "서랍장", "소파", "캐리어", "유모차"),
        "category": "대형폐기물",
        "method": "지역 대형폐기물 신고 페이지에서 품목과 규격을 선택하고 수수료를 납부한 뒤 지정일에 배출합니다.",
        "caution": "신고번호 등 지자체가 요구하는 배출 표시를 부착합니다.",
        "bulky": True,
        "relatedFunction": "get_bulky_waste_report_url(district)",
    },
    {
        "item": "음식물쓰레기",
        "aliases": ("남은 음식", "음식물", "과일 껍질", "채소"),
        "category": "음식물류 폐기물",
        "method": "물기와 이물질을 제거해 지역 전용 용기·봉투 또는 납부필증 방식으로 배출합니다.",
        "caution": "동물 뼈·조개껍데기·과일 씨·티백 등은 일반쓰레기로 분류합니다.",
        "bulky": False,
    },
    {
        "item": "뼈·조개껍데기",
        "aliases": ("닭뼈", "생선뼈", "소뼈", "조개껍질", "게껍질", "달걀껍데기", "과일 씨", "복숭아씨"),
        "category": "일반쓰레기",
        "method": "종량제봉투에 버립니다.",
        "caution": "딱딱해 사료·퇴비화하기 어려운 것은 음식물쓰레기에 넣지 않습니다.",
        "bulky": False,
    },
)


BULKY_WASTE_REPORT_URLS = {
    "종로구": "https://www.jongno.go.kr/waste/pc/web/main/main.do",
    "성북구": "https://smartclean.sb.go.kr/online/bulky/request",
    "수원시": "https://waste.suwon.go.kr",
}


class PublicDataError(RuntimeError):
    """공공데이터 API 호출 또는 응답 형식 오류."""


def normalize_area(area: str) -> str:
    """사용자 입력을 7개 표준 생활권 이름 중 하나로 변환한다."""
    value = area.strip().replace(" ", "")
    for canonical, profile in AREA_PROFILES.items():
        candidates = (canonical, *profile["aliases"])
        if value in {candidate.replace(" ", "") for candidate in candidates}:
            return canonical
    raise ValueError(f"지원하지 않는 지역입니다: {area}")


def get_area_profile(area: str) -> dict[str, Any]:
    """생활권의 시도·시군구·관련 행정동 정보를 반환한다."""
    canonical = normalize_area(area)
    return {"area": canonical, **AREA_PROFILES[canonical]}


def normalize_district(district: str) -> str:
    """입력한 구 이름을 화면에서 사용하는 5개 표준 구 이름으로 변환한다."""
    value = district.strip().replace(" ", "")
    for canonical in DISTRICT_PROFILES:
        if value in {canonical, canonical.removesuffix("구")}:
            return canonical
    raise ValueError(f"지원하지 않는 구입니다: {district}")


def get_district_profile(district: str) -> dict[str, Any]:
    """구의 공공 API 조회값과 선택 가능한 동 목록을 반환한다."""
    canonical = normalize_district(district)
    return {"district": canonical, **DISTRICT_PROFILES[canonical]}


def get_supported_regions() -> list[dict[str, Any]]:
    """웹의 구·동 선택 메뉴를 만들 수 있는 지역 목록을 반환한다."""
    regions = []
    for district, profile in DISTRICT_PROFILES.items():
        labels = profile.get("labels", {})
        regions.append(
            {
                "district": district,
                "dongs": [
                    {"value": dong, "label": labels.get(dong, dong)}
                    for dong in profile["dongs"]
                ],
            }
        )
    return regions


def get_disposal_guide_items() -> list[str]:
    """검색창 자동완성 등에 사용할 대표 품목명을 반환한다."""
    return [str(guide["item"]) for guide in DISPOSAL_GUIDES]


def _normalize_search_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


def search_disposal_guide(
    query: str,
    district: str | None = None,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """품목명으로 분류·배출 방법·주의사항을 검색한다.

    ``district``를 전달하면 지역 규정 확인이 필요한 대형폐기물 결과에 해당
    지자체의 공식 신고 페이지도 포함한다. 찾지 못한 품목을 임의 분류하지 않는다.
    """
    if limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        raise ValueError("검색할 품목명을 입력해 주세요.")

    district_name = None
    report_url = None
    if district is not None:
        profile = _resolve_district(district)
        district_name = profile["district"]
        report_url = get_bulky_waste_report_url(district_name)

    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, guide in enumerate(DISPOSAL_GUIDES):
        names = (str(guide["item"]), *guide.get("aliases", ()))
        normalized_names = [_normalize_search_text(name) for name in names]
        if normalized_query in normalized_names:
            score = 0
        elif any(normalized_query in name for name in normalized_names):
            score = 1
        elif any(name in normalized_query for name in normalized_names):
            score = 2
        else:
            continue
        ranked.append((score, index, guide))

    results = []
    for _, _, guide in sorted(ranked)[:limit]:
        result = {
            key: value
            for key, value in guide.items()
            if key != "aliases"
        }
        result["matchedAliases"] = list(guide.get("aliases", ()))
        result["sources"] = [
            SEOUL_DISPOSAL_GUIDE_SOURCE,
            MINISTRY_RECYCLING_SOURCE,
        ]
        if guide["item"] == "폐의약품":
            result["sources"].append(SEOUL_MEDICINE_SOURCE)
        if report_url and guide.get("bulky") in {True, "depends_on_size", "local_rule"}:
            result["district"] = district_name
            result["reportUrl"] = report_url
        results.append(result)

    if not results:
        return {
            "status": "not_found",
            "query": query.strip(),
            "results": [],
            "message": (
                "등록되지 않은 품목입니다. 임의로 분류하지 말고 제품의 분리배출 "
                "표시 또는 관할 지자체 안내를 확인해 주세요."
            ),
        }
    return {
        "status": "ok",
        "query": query.strip(),
        "district": district_name,
        "results": results,
    }


def _resolve_district(value: str) -> dict[str, Any]:
    """구 입력을 우선 사용하고, 이전 생활권 입력도 호환한다."""
    try:
        return get_district_profile(value)
    except ValueError:
        area = get_area_profile(value)
        district = area.get("gu") or area["sigungu"]
        return get_district_profile(district)


def _normalize_dong(dong: str) -> str:
    value = dong.strip().replace(" ", "")
    return DONG_ALIASES.get(value, value)


def get_waste_schedule(district: str, dong: str | None = None) -> dict[str, Any]:
    """생활쓰레기 배출 일정을 반환한다.

    새 호출 방식은 ``get_waste_schedule("성북구", "보문동")``이다.
    이전 생활권 입력도 호환하며, 구만 입력하면 선택 가능한 동을 반환한다.
    """
    try:
        profile = get_district_profile(district)
        legacy_area = None
    except ValueError:
        legacy_area = get_area_profile(district)
        profile = _resolve_district(district)

    if dong is not None:
        chosen = _normalize_dong(dong)
    elif legacy_area is not None and len(legacy_area["admin_dongs"]) == 1:
        chosen = legacy_area["admin_dongs"][0]
    else:
        return {
            "district": profile["district"],
            "status": "dong_required",
            "dongs": profile["dongs"],
            "message": "정확한 배출 일정을 위해 동을 선택해 주세요.",
        }

    if chosen not in profile["dongs"]:
        raise ValueError(f"{profile['district']}의 지원 동이 아닙니다: {chosen}")

    schedule = WASTE_SCHEDULES.get(chosen)
    if schedule is None:
        return {
            "district": profile["district"],
            "dong": chosen,
            "status": "verification_required",
            "message": "공식 세부 배출표를 확인한 뒤 내부 데이터에 등록해야 합니다.",
        }
    return {"district": profile["district"], "dong": chosen, "status": "ok", **schedule}


def get_bulky_waste_report_url(district: str) -> str:
    """구에 맞는 지자체 공식 대형폐기물 신고 페이지를 반환한다."""
    profile = _resolve_district(district)
    report_key = "수원시" if profile["api_sigungu"] == "수원시" else profile["district"]
    return BULKY_WASTE_REPORT_URLS[report_key]


def _api_key(api_key: str | None) -> str:
    key = api_key or os.getenv("DATA_GO_KR_API_KEY")
    if not key:
        raise ValueError("api_key 또는 DATA_GO_KR_API_KEY 환경변수가 필요합니다.")
    # 포털 화면에 Encoding 키만 보이는 경우도 같은 함수로 사용할 수 있게 한다.
    return unquote(key.strip())


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """공공데이터포털에서 사용되는 여러 JSON 포장을 단일 목록으로 변환한다."""
    response = payload.get("response", payload)
    header = response.get("header", {}) if isinstance(response, dict) else {}
    result_code = str(header.get("resultCode", "00"))
    if result_code not in {"00", "0", "NORMAL_SERVICE"}:
        message = header.get("resultMsg") or header.get("resultMessage") or result_code
        if result_code == "03" or "NODATA" in str(message).replace("_", "").upper():
            return []
        raise PublicDataError(f"공공데이터 API 오류: {message}")

    body = response.get("body", response) if isinstance(response, dict) else response
    items = body.get("items", []) if isinstance(body, dict) else body
    if isinstance(items, dict):
        items = items.get("item", items.get("data", []))
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if not isinstance(items, list):
        raise PublicDataError("API 응답의 items 형식을 해석할 수 없습니다.")
    return [item for item in items if isinstance(item, dict)]


def call_public_data_api(
    endpoint: str,
    *,
    api_key: str | None = None,
    page: int = 1,
    rows: int = 1000,
    timeout: float = 10.0,
    **filters: Any,
) -> list[dict[str, Any]]:
    """공공데이터포털 표준 REST API를 호출해 항목 목록만 반환한다."""
    if page < 1 or not 1 <= rows <= 1000:
        raise ValueError("page는 1 이상, rows는 1~1000이어야 합니다.")
    params = {
        "serviceKey": _api_key(api_key),
        "pageNo": page,
        "numOfRows": rows,
        "type": "json",
        **{key: value for key, value in filters.items() if value not in (None, "")},
    }
    request = Request(f"{endpoint}?{urlencode(params)}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise PublicDataError(f"공공데이터 API 호출 실패: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PublicDataError(f"JSON이 아닌 응답을 받았습니다: {raw[:160]}") from exc
    return _extract_items(payload)


def _get_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _filter_items_for_district(
    items: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """수원시 API 결과를 장안·팔달·권선구 주소로 한 번 더 거른다."""
    address_filter = profile.get("address_filter")
    if not address_filter:
        return items
    address_keys = (
        "lctnRoadNm",
        "lctnLotnoAddr",
        "소재지도로명주소",
        "소재지지번주소",
        "roadAddress",
        "lotAddress",
    )
    return [
        item
        for item in items
        if address_filter
        in " ".join(str(item.get(key, "")) for key in address_keys)
    ]


def _filter_items_for_dong(
    items: list[dict[str, Any]], dong: str | None
) -> list[dict[str, Any]]:
    """내부 표준 필드 또는 주소를 이용해 선택한 동만 남긴다."""
    if dong is None:
        return items
    chosen = _normalize_dong(dong)
    return [
        item
        for item in items
        if chosen
        in " ".join(
            str(item.get(key, "")).strip()
            for key in (
                "adminDong",
                "lctnRoadNm",
                "lctnLotnoAddr",
                "소재지도로명주소",
                "소재지지번주소",
            )
        )
    ]


def _get_seongbuk_battery_lamp_boxes(
    *, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """성북구가 공개한 CSV 236건을 내려받아 공통 필드로 변환한다.

    이 파일은 공공데이터포털에서 로그인이나 인증키 없이 다운로드할 수 있다.
    원본이 CP949로 저장돼 있어 해당 인코딩으로 읽는다.
    """
    request = Request(
        SEONGBUK_BATTERY_LAMP_CSV,
        headers={"User-Agent": "SKKU-waste-course-project/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise PublicDataError(f"성북구 수거함 CSV 호출 실패: {exc}") from exc

    try:
        text = raw.decode("cp949")
    except UnicodeDecodeError:
        text = raw.decode("utf-8-sig")

    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        dong = str(row.get("관리부서(동)명", "")).strip()
        address = str(row.get("주소", "")).strip()
        if dong not in DISTRICT_PROFILES["성북구"]["dongs"]:
            continue
        rows.append(
            {
                "clctKndNm": "폐건전지·폐형광등",
                "lctnRoadNm": address,
                "placeName": str(row.get("위치", "")).strip(),
                "adminDong": dong,
                "lat": str(row.get("위도", "")).strip(),
                "lot": str(row.get("경도", "")).strip(),
                "source": SEONGBUK_BOX_SOURCE,
                "dataSource": "official_csv_fallback",
                "verified": True,
            }
        )
    return rows


def _call_smart_seoul_map(
    theme_id: str,
    subcategories: tuple[str, ...],
    *,
    latitude: float = 37.5868290,
    longitude: float = 127.0006022,
    limit: int = 1000,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """스마트서울맵의 공개 테마 목록을 조회한다(별도 인증키 불필요)."""
    theme_list = json.dumps(
        [{"themeId": theme_id, "subcates": list(subcategories)}],
        ensure_ascii=False,
    )
    body = urlencode(
        {
            "cmd": "getContentsList",
            "themeList": theme_list,
            "longitude": longitude,
            "latitude": latitude,
            "limit": limit,
            "offset": 0,
            "sort": "distanceAsc",
        }
    ).encode("utf-8")
    request = Request(
        SMART_SEOUL_MAP_API,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "SKKU-waste-course-project/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PublicDataError(f"스마트서울맵 조회 실패: {exc}") from exc

    if payload.get("header", {}).get("process") != "success":
        raise PublicDataError("스마트서울맵이 정상 응답을 반환하지 않았습니다.")
    result = payload.get("body", {}).get("result", [])
    return [item for item in result if isinstance(item, dict)]


def _smart_seoul_item(item: dict[str, Any], waste_name: str) -> dict[str, Any]:
    """스마트서울맵 필드를 나머지 수거함 함수와 같은 형태로 변환한다."""
    old_address = str(item.get("cot_addr_full_old", "")).strip()
    legal_dong = old_address.split()[-2] if len(old_address.split()) >= 2 else ""
    return {
        "clctKndNm": waste_name,
        "lctnRoadNm": str(item.get("cot_addr_full_new", "")).strip(),
        "lctnLotnoAddr": old_address,
        "placeName": str(item.get("cot_conts_name", "")).strip(),
        "facilityType": str(item.get("sub_cate_name", "")).strip(),
        "adminDong": legal_dong,
        "lat": item.get("cot_coord_y"),
        "lot": item.get("cot_coord_x"),
        "collectionBoxId": item.get("cot_conts_id"),
        "source": SMART_SEOUL_MAP_GUIDE,
        "dataSource": "smart_seoul_map_current_theme",
        "verified": True,
    }


def _get_jongno_battery_lamp_boxes() -> list[dict[str, Any]]:
    """혜화동·명륜1~4가의 현재 서울시 공개 지도 수거함을 반환한다."""
    items = _call_smart_seoul_map(
        SMART_SEOUL_BATTERY_LAMP_THEME_ID,
        ("2", "3"),
        limit=300,
    )
    target_names = ("혜화동", "명륜1가", "명륜2가", "명륜3가", "명륜4가")
    result = []
    for item in items:
        old_address = str(item.get("cot_addr_full_old", ""))
        if "종로구" not in old_address or not any(
            name in old_address for name in target_names
        ):
            continue
        converted = _smart_seoul_item(item, "폐건전지·폐형광등")
        # 서비스에서는 다섯 법정동을 하나의 행정동 선택지로 묶는다.
        converted["adminDong"] = "혜화동"
        result.append(converted)
    return result


def _get_jongno_medicine_boxes() -> list[dict[str, Any]]:
    """서울시 공개 지도에 현재 등재된 종로구 폐의약품 수거함을 반환한다."""
    items = _call_smart_seoul_map(
        SMART_SEOUL_MEDICINE_THEME_ID,
        ("1", "2", "3", "4", "5"),
        limit=1000,
    )
    return [
        _smart_seoul_item(item, "폐의약품")
        for item in items
        if "종로구"
        in " ".join(
            str(item.get(key, ""))
            for key in ("cot_addr_full_new", "cot_addr_full_old")
        )
    ]


def get_medicine_boxes(
    district: str,
    api_key: str | None = None,
    dong: str | None = None,
) -> list[dict[str, Any]]:
    """선택한 구의 폐의약품 수거함을 조회한다."""
    profile = _resolve_district(district)
    items = call_public_data_api(
        MEDICINE_BOX_API,
        api_key=api_key,
        ctpvNm=profile["sido"],
        sggNm=profile["api_sigungu"],
    )
    items = _filter_items_for_district(items, profile)
    if not items and profile["district"] == "종로구":
        items = _get_jongno_medicine_boxes()
    return _filter_items_for_dong(items, dong)


def get_battery_lamp_boxes(
    district: str,
    api_key: str | None = None,
    dong: str | None = None,
) -> list[dict[str, Any]]:
    """선택한 구의 폐건전지·폐형광등 수거함을 조회한다.

    전국 표준 API 결과가 비어 있으면 서울시 스마트서울맵, 성북구 공식 CSV,
    또는 수원시 공식 행정복지센터 거점 목록으로 자동 전환한다.
    """
    profile = _resolve_district(district)
    items = call_public_data_api(
        BATTERY_LAMP_BOX_API,
        api_key=api_key,
        ctpvNm=profile["sido"],
        sggNm=profile["api_sigungu"],
    )
    items = _filter_items_for_district(items, profile)
    if not items and profile["district"] == "종로구":
        items = _get_jongno_battery_lamp_boxes()
    elif not items and profile["district"] == "성북구":
        items = _get_seongbuk_battery_lamp_boxes()
    if not items:
        items = [
            dict(item)
            for item in STATIC_BATTERY_LAMP_BOXES.get(profile["district"], [])
        ]
    return _filter_items_for_dong(items, dong)


def get_bulky_waste_fees(
    district: str,
    item_keyword: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """지역별 대형폐기물 수수료를 조회하고 선택적으로 품목명을 검색한다."""
    profile = _resolve_district(district)
    items = call_public_data_api(
        BULKY_WASTE_FEE_API,
        api_key=api_key,
        ctpvNm=profile["sido"],
        sggNm=profile["api_sigungu"],
    )
    if not item_keyword:
        return items
    keyword = item_keyword.casefold()
    return [
        item
        for item in items
        if keyword
        in str(_get_value(item, "larWasNm", "대형폐기물명", "wasteName") or "").casefold()
    ]


def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
    lat = _get_value(item, "lat", "위도", "latitude")
    lon = _get_value(item, "lot", "경도", "longitude", "lon")
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_boxes(
    items: Iterable[dict[str, Any]],
    latitude: float,
    longitude: float,
    *,
    limit: int = 5,
    max_distance_km: float | None = None,
) -> list[dict[str, Any]]:
    """API 결과를 사용자 좌표와 가까운 순서로 정렬한다."""
    if limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")
    ranked = []
    for item in items:
        point = _coordinates(item)
        if point is None:
            continue
        distance = _distance_km(latitude, longitude, *point)
        if max_distance_km is None or distance <= max_distance_km:
            ranked.append({**item, "distance_km": round(distance, 3)})
    ranked.sort(key=lambda item: item["distance_km"])
    return ranked[:limit]


def find_nearest_collection_boxes(
    district: str,
    waste_type: str,
    latitude: float,
    longitude: float,
    *,
    api_key: str | None = None,
    dong: str | None = None,
    limit: int = 5,
    max_distance_km: float | None = 5.0,
) -> list[dict[str, Any]]:
    """폐의약품 또는 폐건전지·폐형광등 수거함을 가까운 순으로 조회한다."""
    normalized = waste_type.strip().replace(" ", "")
    if normalized in {"폐의약품", "의약품"}:
        all_items = get_medicine_boxes(district, api_key, None)
        # 실제 좌표가 있으면 행정동 경계를 먼저 적용하지 않고 선택한 구 전체에서
        # 거리를 계산한다. 경계 바로 건너편의 더 가까운 수거함이 누락되는 것을 막는다.
        items = all_items
    elif normalized in {"폐건전지", "건전지", "폐형광등", "형광등"}:
        items = get_battery_lamp_boxes(district, api_key, None)
        keyword = "건전지" if "건전지" in normalized else "형광등"
        items = [
            item
            for item in items
            if keyword
            in str(_get_value(item, "clctKndNm", "수거종류", "수거품목") or "").replace("폐", "")
        ] or items
    else:
        raise ValueError("waste_type은 폐의약품, 폐건전지, 폐형광등 중 하나여야 합니다.")
    return nearest_boxes(
        items,
        latitude,
        longitude,
        limit=limit,
        max_distance_km=max_distance_km,
    )


if __name__ == "__main__":
    # 인증키 없이도 구·동 메뉴와 내부 배출 일정은 바로 확인할 수 있다.
    print(json.dumps(get_supported_regions(), ensure_ascii=False, indent=2))
    print(json.dumps(get_waste_schedule("성북구", "보문동"), ensure_ascii=False, indent=2))
