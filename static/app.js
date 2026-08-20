"use strict";

const state = { regions: [], position: null, kind: "폐의약품", markers: [] };
const supportedLocationAnchors = [
  { district: "종로구", dong: "혜화동", lat: 37.586829, lon: 127.000602 },
  { district: "성북구", dong: "삼선동", lat: 37.5901, lon: 127.0144 },
  { district: "성북구", dong: "성북동", lat: 37.5939, lon: 127.0036 },
  { district: "성북구", dong: "동선동", lat: 37.5934, lon: 127.0207 },
  { district: "성북구", dong: "보문동", lat: 37.5804, lon: 127.0228 },
  { district: "장안구", dong: "율천동", lat: 37.2976195, lon: 126.9714636 },
  { district: "팔달구", dong: "화서1동", lat: 37.2764022, lon: 126.9950268 },
  { district: "팔달구", dong: "화서2동", lat: 37.2850707, lon: 126.9863215 },
  { district: "권선구", dong: "구운동", lat: 37.2771517, lon: 126.9714384 },
];
const $ = (selector) => document.querySelector(selector);
const district = $("#district");
const dong = $("#dong");
const toast = $("#toast");
const map = L.map("map", { zoomControl: true }).setView([37.575, 127.005], 12);
const markerLayer = L.layerGroup().addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 4200);
}

async function api(path, params = {}) {
  const url = new URL(path, location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") url.searchParams.set(key, value);
  });
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) throw new Error(body.message || "정보를 불러오지 못했습니다.");
  return body;
}

function selectedRegion() {
  return { district: district.value, dong: dong.value };
}

function distanceKm(lat1, lon1, lat2, lon2) {
  const toRadians = (value) => value * Math.PI / 180;
  const radius = 6371.0088;
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
  return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function nearestSupportedLocation(lat, lon) {
  const ranked = supportedLocationAnchors.map((item) => ({
    ...item,
    distanceKm: distanceKm(lat, lon, item.lat, item.lon),
  })).sort((a, b) => a.distanceKm - b.distanceKm);
  return ranked[0]?.distanceKm <= 5 ? ranked[0] : null;
}

function fillDongs() {
  const region = state.regions.find((item) => item.district === district.value);
  dong.innerHTML = (region?.dongs || []).map((item) =>
    `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`
  ).join("");
}

function scheduleBlocks(schedule) {
  const labels = { general_food: "일반·음식물", recycle: "재활용", all_waste: "생활쓰레기" };
  const blocks = Object.entries(labels).filter(([key]) => schedule[key]).map(([key, label]) => {
    const value = schedule[key];
    return `<div class="schedule-block"><strong>${label}</strong><b>${escapeHtml(value.days.join(" · "))}</b><div>${escapeHtml(value.time)}</div></div>`;
  });
  const notice = schedule.notice ? `<p class="notice">${escapeHtml(schedule.notice)}</p>` : "";
  const source = schedule.source ? `<a class="official-link" href="${escapeHtml(schedule.source)}" target="_blank" rel="noopener noreferrer">공식 근거 확인 ↗</a>` : "";
  return blocks.join("") + notice + source;
}

async function loadSchedule() {
  const target = $("#schedule");
  target.className = "result muted";
  target.textContent = "일정을 확인하는 중…";
  try {
    const body = await api("/api/schedule", selectedRegion());
    target.className = "result";
    target.innerHTML = scheduleBlocks(body.schedule);
  } catch (error) { target.textContent = error.message; showToast(error.message); }
}

async function loadBoxes() {
  const target = $("#box-list");
  target.className = "box-list muted";
  target.textContent = "수거함 위치를 확인하는 중…";
  const params = { ...selectedRegion(), kind: state.kind };
  if (state.position) Object.assign(params, { lat: state.position.lat, lon: state.position.lon });
  try {
    const body = await api("/api/boxes", params);
    renderBoxes(body.boxes);
  } catch (error) {
    markerLayer.clearLayers();
    target.textContent = error.message;
    showToast(error.message);
  }
}

function renderBoxes(boxes) {
  const target = $("#box-list");
  markerLayer.clearLayers();
  const points = [];
  if (!boxes.length) {
    target.className = "box-list muted";
    target.textContent = "선택한 지역에서 확인된 수거함이 없습니다. 관할 주민센터에 문의해 주세요.";
    return;
  }
  target.className = "box-list";
  target.innerHTML = boxes.map((box, index) => {
    if (box.lat !== null && box.lon !== null) {
      const marker = L.marker([box.lat, box.lon]).bindPopup(`<b>${escapeHtml(box.name)}</b><br>${escapeHtml(box.address)}`);
      marker.addTo(markerLayer); state.markers[index] = marker; points.push([box.lat, box.lon]);
    }
    const distance = box.distanceKm !== null ? `<span class="distance">${box.distanceKm.toFixed(2)} km</span>` : "";
    return `<button class="box-item" data-index="${index}" type="button"><strong>${escapeHtml(box.name)}</strong><span>${escapeHtml(box.address)}</span>${distance}</button>`;
  }).join("");
  if (state.position) {
    L.circleMarker([state.position.lat, state.position.lon], { radius: 8, color: "#176b48", fillColor: "#dff16f", fillOpacity: 1 }).bindPopup("내 위치").addTo(markerLayer);
    points.push([state.position.lat, state.position.lon]);
  }
  if (points.length) map.fitBounds(points, { padding: [35, 35], maxZoom: 15 });
  target.querySelectorAll(".box-item").forEach((button) => button.addEventListener("click", () => {
    const marker = state.markers[Number(button.dataset.index)];
    if (marker) { map.setView(marker.getLatLng(), 16); marker.openPopup(); }
  }));
}

async function searchGuide(event) {
  event.preventDefault();
  const query = $("#guide-query").value.trim();
  const target = $("#guide-result");
  if (!query) return showToast("검색할 품목명을 입력해 주세요.");
  target.textContent = "배출 방법을 찾는 중…";
  try {
    const body = await api("/api/search", { q: query, district: district.value });
    if (!body.results.length) { target.className = "result muted"; target.textContent = body.message; return; }
    target.className = "result";
    target.innerHTML = body.results.map((item) => `<article class="guide-card"><span class="pill">${escapeHtml(item.category)}</span><h3>${escapeHtml(item.item)}</h3><p>${escapeHtml(item.method)}</p><p class="caution">주의 · ${escapeHtml(item.caution)}</p>${item.reportUrl ? `<a class="official-link" href="${escapeHtml(item.reportUrl)}" target="_blank" rel="noopener noreferrer">공식 신고 페이지 ↗</a>` : ""}</article>`).join("");
  } catch (error) { target.textContent = error.message; showToast(error.message); }
}

async function searchBulky(event) {
  event.preventDefault();
  const query = $("#bulky-query").value.trim();
  const target = $("#bulky-result");
  target.textContent = "수수료를 확인하는 중…";
  try {
    const body = await api("/api/bulky", { q: query, district: district.value });
    const rows = body.fees.length ? `<table class="fee-table"><thead><tr><th>품목</th><th>규격</th><th>수수료</th></tr></thead><tbody>${body.fees.map((fee) => `<tr><td>${escapeHtml(fee.name)}</td><td>${escapeHtml(fee.detail)}</td><td>${escapeHtml(fee.fee)}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">일치하는 수수료 항목을 찾지 못했습니다. 공식 신고 페이지에서 직접 확인해 주세요.</p>`;
    target.className = "result";
    target.innerHTML = rows + `<a class="official-link" href="${escapeHtml(body.reportUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(district.value)} 공식 대형폐기물 신고 ↗</a>`;
  } catch (error) { target.textContent = error.message; showToast(error.message); }
}

function locate() {
  const status = $("#location-status");
  const button = $("#locate");
  if (!navigator.geolocation) return showToast("이 브라우저는 위치 기능을 지원하지 않습니다.");
  status.textContent = "현재 위치를 확인하는 중…";
  button.disabled = true;
  navigator.geolocation.getCurrentPosition(async (position) => {
    state.position = { lat: position.coords.latitude, lon: position.coords.longitude };
    const matched = nearestSupportedLocation(state.position.lat, state.position.lon);
    if (!matched) {
      status.textContent = "현재 위치가 지원 지역에서 멀어 기존 지역 선택을 유지합니다. 위치는 저장하지 않습니다.";
      button.disabled = false;
      await loadBoxes();
      return showToast("현재 위치와 가까운 지원 지역을 찾지 못했습니다.");
    }

    district.value = matched.district;
    fillDongs();
    dong.value = matched.dong;
    status.textContent = `${matched.district} ${dong.options[dong.selectedIndex].text}으로 자동 선택했습니다. 위치는 저장하지 않습니다.`;

    const refreshes = [loadSchedule(), loadBoxes()];
    if ($("#guide-query").value.trim()) refreshes.push(searchGuide(new Event("submit")));
    if ($("#bulky-query").value.trim()) refreshes.push(searchBulky(new Event("submit")));
    await Promise.all(refreshes);
    button.disabled = false;
    showToast("현재 위치 기준으로 지역과 정보를 갱신했습니다.");
  }, (error) => {
    button.disabled = false;
    status.textContent = "위치 권한 없이도 구·동 기준으로 이용할 수 있습니다.";
    const messages = {
      1: "위치 권한이 거부되었습니다. Edge 또는 Chrome의 주소창 왼쪽 사이트 권한에서 위치를 허용해 주세요.",
      2: "현재 위치를 확인할 수 없습니다. Windows 위치 서비스를 켜고 다시 시도해 주세요.",
      3: "위치 확인 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
    };
    showToast(messages[error.code] || "위치를 확인하지 못했습니다. 브라우저 위치 설정을 확인해 주세요.");
  }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 });
}

async function init() {
  try {
    const [regionBody, itemBody] = await Promise.all([api("/api/regions"), api("/api/items")]);
    state.regions = regionBody.regions;
    district.innerHTML = state.regions.map((item) => `<option value="${escapeHtml(item.district)}">${escapeHtml(item.district)}</option>`).join("");
    $("#item-list").innerHTML = itemBody.items.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("");
    fillDongs(); await Promise.all([loadSchedule(), loadBoxes()]);
  } catch (error) { showToast(error.message); }
}

district.addEventListener("change", () => { fillDongs(); loadSchedule(); loadBoxes(); });
dong.addEventListener("change", () => { loadSchedule(); loadBoxes(); });
$("#locate").addEventListener("click", locate);
$("#guide-form").addEventListener("submit", searchGuide);
$("#bulky-form").addEventListener("submit", searchBulky);
document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
  button.classList.add("active"); state.kind = button.dataset.kind; loadBoxes();
}));
init();
