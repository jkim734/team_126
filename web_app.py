"""Public web interface for the SKKU everyday waste guide.

The public-data API key is read only by this server.  It is never rendered into
HTML or returned from an endpoint.
"""

from __future__ import annotations

import math
import os
from typing import Any, Callable

from flask import Flask, Response, jsonify, render_template, request

import waste_api


app = Flask(__name__)
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

SITE_URL = os.getenv("SITE_URL", "https://team-126-qd9y.vercel.app").rstrip("/")

BULKY_SEARCH_ALIASES = {
    "매트리스": "침대",
    "매트리스침대": "침대",
    "쇼파": "소파",
    "장농": "장롱",
}


def _server_api_key() -> str:
    """Return the server-only key without exposing it to a response."""
    key = app.config.get("DATA_GO_KR_API_KEY") or os.getenv("DATA_GO_KR_API_KEY")
    if not key:
        raise ValueError("DATA_GO_KR_API_KEY 환경변수가 필요합니다.")
    return str(key).strip()


def _error(message: str, status: int = 400):
    return jsonify({"ok": False, "message": message}), status


def _query(name: str, *, required: bool = True, max_length: int = 80) -> str | None:
    value = request.args.get(name, type=str)
    if value is not None:
        value = value.strip()
    if required and not value:
        raise ValueError(f"{name} 값을 입력해 주세요.")
    if value and len(value) > max_length:
        raise ValueError(f"{name} 값이 너무 깁니다.")
    return value or None


def _coordinate(name: str) -> float | None:
    raw = request.args.get(name, type=str)
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("위치 좌표 형식이 올바르지 않습니다.") from exc
    limit = 90 if name == "lat" else 180
    if not math.isfinite(value) or not -limit <= value <= limit:
        raise ValueError("위치 좌표 범위를 확인해 주세요.")
    return value


def _first(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return value
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _box_view(item: dict[str, Any]) -> dict[str, Any]:
    """Expose a stable, minimal shape despite differing public-data schemas."""
    return {
        "name": _first(
            item,
            "placeName",
            "fcltyNm",
            "instlPlaceNm",
            "수거함명",
            "설치장소명",
        ) or "수거 장소",
        "address": _first(
            item,
            "lctnRoadNm",
            "lctnLotnoAddr",
            "roadAddress",
            "lotAddress",
            "소재지도로명주소",
            "소재지지번주소",
        ) or "주소 정보 없음",
        "kind": _first(item, "clctKndNm", "수거종류", "수거품목") or "",
        "lat": _float_or_none(_first(item, "lat", "latitude", "위도")),
        "lon": _float_or_none(_first(item, "lot", "lon", "longitude", "경도")),
        "distanceKm": _float_or_none(item.get("distance_km")),
        "source": item.get("source"),
        "verified": bool(item.get("verified", False)),
    }


def _fee_view(item: dict[str, Any]) -> dict[str, Any]:
    name = _first(item, "larWasNm", "대형폐기물명", "wasteName", "품목명")
    detail = _first(
        item,
        "larWasSpcfct",
        "larWasSpec",
        "대형폐기물규격",
        "규격",
        "wasteSpec",
        "규격명",
    )
    fee = _first(
        item,
        "fee",
        "수수료",
        "charge",
        "collectionFee",
        "처리비용",
        "수수료금액",
    )
    return {
        "name": str(name or "품목명 미제공"),
        "detail": str(detail or "규격은 신고 페이지에서 확인"),
        "fee": str(fee or "신고 페이지에서 확인"),
    }


def _public_call(callback: Callable[[], Any]):
    try:
        return callback()
    except ValueError as exc:
        message = str(exc)
        if "DATA_GO_KR_API_KEY" in message or "api_key" in message:
            return _error(
                "서버에 공공데이터 인증키가 설정되지 않았습니다. 관리자에게 알려 주세요.",
                503,
            )
        return _error(message, 400)
    except waste_api.PublicDataError:
        app.logger.exception("Public data provider request failed")
        return _error(
            "공공데이터 서버 연결이 원활하지 않습니다. 잠시 뒤 다시 시도해 주세요.",
            502,
        )
    except Exception:
        app.logger.exception("Unexpected request failure")
        return _error("일시적인 오류가 발생했습니다. 잠시 뒤 다시 시도해 주세요.", 500)


@app.get("/")
def index():
    return render_template(
        "index.html",
        analytics_measurement_id=os.getenv("GA_MEASUREMENT_ID", "").strip(),
        google_site_verification=os.getenv(
            "GOOGLE_SITE_VERIFICATION", ""
        ).strip(),
        site_url=SITE_URL,
    )


@app.get("/privacy")
def privacy():
    return render_template("privacy.html", site_url=SITE_URL)


@app.get("/robots.txt")
def robots():
    body = f"User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    return Response(body, content_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml")
def sitemap():
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE_URL}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>{SITE_URL}/privacy</loc><changefreq>yearly</changefreq><priority>0.2</priority></url>
</urlset>
"""
    return Response(body, content_type="application/xml; charset=utf-8")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "일상기술 쓰레기 안내"})


@app.get("/api/regions")
def regions():
    return jsonify({"ok": True, "regions": waste_api.get_supported_regions()})


@app.get("/api/items")
def items():
    return jsonify({"ok": True, "items": waste_api.get_disposal_guide_items()})


@app.get("/api/schedule")
def schedule():
    def run():
        district = _query("district")
        dong = _query("dong")
        return jsonify(
            {"ok": True, "schedule": waste_api.get_waste_schedule(district, dong)}
        )

    return _public_call(run)


@app.get("/api/search")
def search():
    def run():
        query = _query("q", max_length=50)
        district = _query("district", required=False)
        return jsonify(
            {"ok": True, **waste_api.search_disposal_guide(query, district)}
        )

    return _public_call(run)


@app.get("/api/boxes")
def boxes():
    def run():
        district = _query("district")
        dong = _query("dong", required=False)
        kind = _query("kind")
        lat, lon = _coordinate("lat"), _coordinate("lon")
        if (lat is None) != (lon is None):
            raise ValueError("위도와 경도를 함께 보내 주세요.")

        if lat is not None and lon is not None:
            data = waste_api.find_nearest_collection_boxes(
                district,
                kind,
                lat,
                lon,
                api_key=_server_api_key(),
                dong=dong,
                limit=30,
                max_distance_km=None,
            )
        elif kind == "폐의약품":
            data = waste_api.get_medicine_boxes(
                district, api_key=_server_api_key(), dong=dong
            )
        elif kind in {"폐건전지", "폐형광등"}:
            data = waste_api.get_battery_lamp_boxes(
                district, api_key=_server_api_key(), dong=dong
            )
            keyword = "건전지" if kind == "폐건전지" else "형광등"
            matching = [
                item
                for item in data
                if keyword in str(_first(item, "clctKndNm", "수거종류", "수거품목") or "")
            ]
            data = matching or data
        else:
            raise ValueError("kind는 폐의약품, 폐건전지, 폐형광등 중 하나여야 합니다.")

        return jsonify({"ok": True, "boxes": [_box_view(item) for item in data[:100]]})

    return _public_call(run)


@app.get("/api/bulky")
def bulky():
    def run():
        district = _query("district")
        keyword = _query("q", required=False, max_length=50)
        api_keyword = BULKY_SEARCH_ALIASES.get(
            (keyword or "").replace(" ", ""), keyword
        )
        fees = waste_api.get_bulky_waste_fees(
            district, api_keyword, api_key=_server_api_key()
        )
        return jsonify(
            {
                "ok": True,
                "fees": [_fee_view(item) for item in fees[:100]],
                "reportUrl": waste_api.get_bulky_waste_report_url(district),
            }
        )

    return _public_call(run)


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return _error_response("요청한 기능을 찾을 수 없습니다.", 404)
    return render_template("index.html"), 404


def _error_response(message: str, status: int):
    return jsonify({"ok": False, "message": message}), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
