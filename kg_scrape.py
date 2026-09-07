"""
KG Hà Nội — Bước 1a + 1b: Thu thập dữ liệu

Bước 1a: Cào bài viết di tích Hà Nội từ Wikipedia tiếng Việt
Bước 1b: Sinh triplets ẩm thực từ CSV curate thủ công

Chạy trên Kaggle:
  !pip install requests -q
  !python kg_scrape.py scrape-landmarks --out /kaggle/working/wiki_raw/
  !python kg_scrape.py scrape-food --out /kaggle/working/food_raw/
  !python kg_scrape.py stats --landmarks /kaggle/working/wiki_raw/ --food /kaggle/working/food_raw/
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from pathlib import Path
from typing import Optional


# ============================================================================ #
#  CONSTANTS
# ============================================================================ #

WIKI_API = "https://vi.wikipedia.org/w/api.php"

# ---------- Categories chứa di tích ----------
WIKI_CATEGORIES = [
    "Di_tích_quốc_gia_đặc_biệt_của_Việt_Nam",
    "Di_tích_lịch_sử_Hà_Nội",
    "Danh_lam_thắng_cảnh_Hà_Nội",
    "Chùa_ở_Hà_Nội",
    "Đền_ở_Hà_Nội",
    "Đình_ở_Hà_Nội",
    "Lăng_tẩm_ở_Hà_Nội",
    "Bảo_tàng_tại_Hà_Nội",
    "Cầu_ở_Hà_Nội",
    "Công_trình_kiến_trúc_ở_Hà_Nội",
    "Phố_cổ_Hà_Nội",
]

# Danh sách di tích cụ thể (đảm bảo không bị thiếu)
EXTRA_LANDMARK_PAGES = [
    # --- Di tích lịch sử cốt lõi ---
    "Văn_Miếu_-_Quốc_Tử_Giám",
    "Chùa_Một_Cột",
    "Hoàng_thành_Thăng_Long",
    "Hồ_Hoàn_Kiếm",
    "Đền_Ngọc_Sơn",
    "Chùa_Trấn_Quốc",
    "Tháp_Rùa_(Hà_Nội)",
    "Cột_cờ_Hà_Nội",
    "Thành_Cổ_Loa",
    "Đền_Quán_Thánh",
    "Chùa_Hương",
    "Lăng_Chủ_tịch_Hồ_Chí_Minh",
    "Phủ_Chủ_tịch",
    "Chùa_Kim_Liên_(Hà_Nội)",
    "Đền_Hai_Bà_Trưng_(Hà_Nội)",
    "Chùa_Tây_Phương",
    "Chùa_Thầy",
    "Đình_Tây_Đằng",
    "Đền_Sóc",
    # --- Kiến trúc Pháp / cận đại ---
    "Nhà_hát_Lớn_Hà_Nội",
    "Nhà_thờ_Lớn_Hà_Nội",
    "Cầu_Long_Biên",
    "Phố_cổ_Hà_Nội",
    "Bảo_tàng_Lịch_sử_Quốc_gia_(Việt_Nam)",
    "Bảo_tàng_Hồ_Chí_Minh",
    "Bảo_tàng_Mỹ_thuật_Việt_Nam",
    "Bảo_tàng_Dân_tộc_học_Việt_Nam",
    "Nhà_tù_Hỏa_Lò",
    # --- Danh lam / công viên ---
    "Hồ_Tây",
    "Công_viên_Thống_Nhất",
    "Vườn_quốc_gia_Ba_Vì",
    "Làng_cổ_Đường_Lâm",
]

# Keywords filter — bài phải chứa ít nhất 1 keyword
HANOI_KEYWORDS = [
    "Hà Nội", "Thăng Long", "Đông Đô", "Kẻ Chợ",
    "Hoàn Kiếm", "Ba Đình", "Đống Đa", "Hai Bà Trưng",
    "Tây Hồ", "Cầu Giấy", "Long Biên", "Thanh Xuân",
    "Hoàng Mai", "Sơn Tây", "Gia Lâm", "Đông Anh",
    "Sóc Sơn", "Mê Linh", "Thanh Trì",
]


# ---------- Dữ liệu ẩm thực (curate thủ công) ----------
FOOD_CSV = """tên_quán,loại_món,quận,địa_chỉ,giá_trung_bình,giờ_mở_cửa,nổi_tiếng_vì,di_tích_gần_nhất,khoảng_cách_km
Phở Thìn Bờ Hồ,Phở,Quận Hai Bà Trưng,13 Lò Đúc,50000,06:00-20:30,Phở xào tái lăn trứ danh,Hồ Hoàn Kiếm,1.0
Phở Gia Truyền Bát Đàn,Phở,Quận Hoàn Kiếm,49 Bát Đàn,40000,06:00-10:00 và 17:00-20:00,Xếp hàng dài từ sáng sớm — chỉ bán phở bò,Đền Quán Thánh,0.8
Phở Lý Quốc Sư,Phở,Quận Hoàn Kiếm,10 Lý Quốc Sư,55000,06:00-22:00,Nước dùng trong thanh đậm đà,Nhà thờ Lớn Hà Nội,0.2
Bún Chả Hương Liên,Bún chả,Quận Hai Bà Trưng,24 Lê Văn Hưu,45000,08:00-20:00,Obama và Anthony Bourdain từng ăn (2016),Hồ Hoàn Kiếm,1.2
Bún Chả Đắc Kim,Bún chả,Quận Hoàn Kiếm,1 Hàng Mành,40000,09:00-14:00,Bún chả lối cổ phố cổ,Đền Ngọc Sơn,0.5
Bún Đậu Homemade,Bún đậu mắm tôm,Quận Đống Đa,29 Ngõ Thổ Quan,40000,10:00-22:00,Bún đậu mắm tôm phong cách trẻ,Văn Miếu – Quốc Tử Giám,0.6
Cà Phê Trứng Giảng,Cà phê trứng,Quận Hoàn Kiếm,39 Nguyễn Hữu Huân,35000,07:00-22:00,Cà phê trứng nguyên bản từ 1946,Đền Ngọc Sơn,0.3
Cà Phê Lâm,Cà phê,Quận Hoàn Kiếm,60 Nguyễn Hữu Huân,30000,07:00-21:00,Quán cà phê trưng bày tranh nghệ sĩ,Đền Ngọc Sơn,0.3
Kem Tràng Tiền,Kem Tràng Tiền,Quận Hoàn Kiếm,35 Tràng Tiền,15000,09:00-22:00,Kem que huyền thoại Hà Nội từ 1958,Nhà hát Lớn Hà Nội,0.2
Xôi Yến,Xôi,Quận Hoàn Kiếm,35B Nguyễn Hữu Huân,25000,06:30-23:00,Xôi đậu xanh thịt nướng đông khách nhất phố cổ,Đền Ngọc Sơn,0.4
Chả Cá Lã Vọng,Chả cá,Quận Hoàn Kiếm,14 Chả Cá,150000,11:00-14:00 và 17:00-21:00,Chả cá truyền thống — phố mang tên món ăn,Đền Quán Thánh,0.6
Bánh Cuốn Bà Hoành,Bánh cuốn,Quận Hoàn Kiếm,66 Tô Hiến Thành,35000,06:30-13:00,Bánh cuốn tráng tay nóng hổi,Hồ Hoàn Kiếm,0.8
Bún Ốc Bà Ngoại,Bún ốc,Quận Hai Bà Trưng,45 Nguyễn Cao,35000,07:00-22:00,Bún ốc nước chua cay đậm vị,Hồ Hoàn Kiếm,1.5
Bánh Mì 25,Bánh mì,Quận Hoàn Kiếm,25 Hàng Cá,25000,07:00-23:00,Bánh mì phố cổ — TripAdvisor top rated,Đền Ngọc Sơn,0.3
Nem Chua Rán Bà Dự,Nem chua rán,Quận Hoàn Kiếm,30 Mã Mây,20000,14:00-22:00,Nem rán giòn rụm ăn vặt phố cổ,Đền Ngọc Sơn,0.4
Lẩu Cua Đồng Bà Vinh,Lẩu cua đồng,Quận Đống Đa,Ngõ 44 Hào Nam,120000,10:00-22:00,Cua đồng xay nguyên con nấu bún,Văn Miếu – Quốc Tử Giám,0.8
Miến Lươn Đông Thịnh,Miến lươn,Quận Hoàn Kiếm,87 Hàng Điếu,45000,08:00-21:00,Miến lươn trộn giòn tan,Đền Quán Thánh,0.4
Bánh Tôm Hồ Tây,Bánh tôm,Quận Tây Hồ,1 Thanh Niên,60000,09:00-21:00,Bánh tôm chiên giòn view Hồ Tây,Chùa Trấn Quốc,0.3
Ốc Béo Cổng Bảo Tàng,Ốc,Quận Ba Đình,Trước 66 Nguyễn Thái Học,50000,16:00-23:00,Ốc luộc ốc xào bơ vỉa hè đông đúc,Cột cờ Hà Nội,0.5
Trà Đá Vỉa Hè Bờ Hồ,Trà đá,Quận Hoàn Kiếm,Bờ Hồ Hoàn Kiếm,5000,06:00-23:00,Trà đá vỉa hè — nét văn hóa Hà Nội,Hồ Hoàn Kiếm,0.1
"""

DISH_INFO = {
    "Phở": {
        "mô_tả": "Món súp truyền thống với bánh phở và nước dùng xương bò hoặc gà",
        "nguồn_gốc": "Nam Định / Hà Nội",
        "đặc_trưng": "Nước dùng ninh xương 12-24 tiếng với quế hồi thảo quả",
    },
    "Bún chả": {
        "mô_tả": "Bún ăn kèm chả nướng than hoa và nước mắm pha chua ngọt",
        "nguồn_gốc": "Hà Nội",
        "đặc_trưng": "Chả viên và chả miếng nướng than hoa",
    },
    "Chả cá": {
        "mô_tả": "Cá lăng ướp nghệ chiên giòn ăn kèm bún thì là hành",
        "nguồn_gốc": "Hà Nội",
        "đặc_trưng": "Phố Chả Cá được đặt tên theo món ăn này",
    },
    "Bún đậu mắm tôm": {
        "mô_tả": "Bún kèm đậu phụ rán chấm mắm tôm",
        "nguồn_gốc": "Hà Nội",
        "đặc_trưng": "Mắm tôm vắt chanh quất đánh bông",
    },
    "Bánh cuốn": {
        "mô_tả": "Bánh bột gạo tráng mỏng nhân thịt mộc nhĩ",
        "nguồn_gốc": "Thanh Trì, Hà Nội",
        "đặc_trưng": "Bánh tráng nóng tại chỗ ăn kèm chả quế",
    },
    "Xôi": {
        "mô_tả": "Gạo nếp đồ chín ăn kèm nhiều topping",
        "nguồn_gốc": "Việt Nam",
        "đặc_trưng": "Xôi xéo đậu xanh mỡ hành là bản Hà Nội",
    },
    "Cà phê trứng": {
        "mô_tả": "Cà phê đánh với lòng đỏ trứng gà và đường",
        "nguồn_gốc": "Hà Nội — sáng tạo bởi ông Nguyễn Văn Giảng năm 1946",
        "đặc_trưng": "Kem trứng béo ngậy phủ trên cà phê đen nóng",
    },
    "Kem Tràng Tiền": {
        "mô_tả": "Kem que truyền thống Hà Nội",
        "nguồn_gốc": "Hà Nội — từ 1958",
        "đặc_trưng": "Kem cốm kem sô-cô-la kem đậu xanh",
    },
    "Bún ốc": {
        "mô_tả": "Bún nước chua cay với ốc luộc hoặc xào",
        "nguồn_gốc": "Hà Nội",
        "đặc_trưng": "Nước dùng cà chua dấm bỗng chua thanh",
    },
    "Bánh mì": {
        "mô_tả": "Bánh mì kẹp thịt pate rau kiểu Việt",
        "nguồn_gốc": "Việt Nam",
        "đặc_trưng": "Vỏ giòn ruột mềm nhân phong phú",
    },
    "Bánh tôm": {
        "mô_tả": "Tôm tươi chiên bột giòn ăn kèm rau sống",
        "nguồn_gốc": "Hà Nội (Hồ Tây)",
        "đặc_trưng": "Tôm tươi Hồ Tây chiên vàng chấm nước mắm",
    },
    "Nem chua rán": {
        "mô_tả": "Nem chua lên men chiên giòn",
        "nguồn_gốc": "Việt Nam",
        "đặc_trưng": "Ăn vặt phổ biến phố cổ Hà Nội",
    },
    "Lẩu cua đồng": {
        "mô_tả": "Lẩu riêu cua đồng nấu bún",
        "nguồn_gốc": "Đồng bằng Bắc Bộ",
        "đặc_trưng": "Cua xay nguyên con gạch cua vàng ươm",
    },
    "Miến lươn": {
        "mô_tả": "Miến dong với lươn xào hoặc lươn nấu nước",
        "nguồn_gốc": "Nghệ An / Hà Nội",
        "đặc_trưng": "Miến trộn lươn chiên giòn rắc hành phi",
    },
    "Ốc": {
        "mô_tả": "Các loại ốc luộc xào nướng — ăn vỉa hè",
        "nguồn_gốc": "Việt Nam",
        "đặc_trưng": "Ốc luộc sả ốc xào bơ tỏi ốc hấp lá gừng",
    },
    "Trà đá": {
        "mô_tả": "Trà xanh pha loãng uống đá — văn hóa vỉa hè Hà Nội",
        "nguồn_gốc": "Hà Nội",
        "đặc_trưng": "Ngồi ghế nhựa vỉa hè nhìn phố — nét đặc trưng thủ đô",
    },
    "Cà phê": {
        "mô_tả": "Cà phê phin truyền thống Việt Nam",
        "nguồn_gốc": "Việt Nam",
        "đặc_trưng": "Cà phê đen đá hoặc nâu đá pha phin",
    },
}

HANOI_DISTRICTS = {
    "Quận Hoàn Kiếm": "Quận trung tâm lịch sử Hà Nội — chứa Hồ Hoàn Kiếm và Phố Cổ",
    "Quận Ba Đình": "Trung tâm chính trị — có Lăng Bác và Hoàng Thành Thăng Long",
    "Quận Đống Đa": "Quận phía nam trung tâm — có Văn Miếu và gò Đống Đa",
    "Quận Hai Bà Trưng": "Quận phía đông nam trung tâm Hà Nội",
    "Quận Tây Hồ": "Quận ven Hồ Tây — có Chùa Trấn Quốc và đường Thanh Niên",
    "Quận Cầu Giấy": "Quận phía tây — khu vực đại học và công nghệ",
    "Quận Long Biên": "Quận phía đông sông Hồng — có Cầu Long Biên",
    "Quận Thanh Xuân": "Quận phía nam Hà Nội",
    "Quận Hoàng Mai": "Quận phía đông nam Hà Nội",
    "Thị xã Sơn Tây": "Thị xã phía tây — có Thành cổ Sơn Tây và Làng cổ Đường Lâm",
    "Huyện Đông Anh": "Huyện phía bắc — có Thành Cổ Loa",
    "Huyện Sóc Sơn": "Huyện phía bắc — có Đền Sóc (Đền Gióng)",
    "Huyện Mỹ Đức": "Huyện phía nam — có Chùa Hương",
    "Huyện Quốc Oai": "Huyện phía tây — có Chùa Thầy",
    "Huyện Thạch Thất": "Huyện phía tây — có Chùa Tây Phương",
    "Huyện Ba Vì": "Huyện phía tây — có Vườn quốc gia Ba Vì",
}


# ============================================================================ #
#  WIKIPEDIA HELPERS
# ============================================================================ #

def _wiki_get(params: dict) -> dict:
    import requests
    params.setdefault("format", "json")
    resp = requests.get(WIKI_API, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_category_members(category: str, limit: int = 500) -> list[str]:
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Thể_loại:{category}",
        "cmlimit": str(min(limit, 500)),
        "cmtype": "page",
    }
    while True:
        data = _wiki_get(params)
        for m in data.get("query", {}).get("categorymembers", []):
            titles.append(m["title"])
        if "continue" in data:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
        else:
            break
    return titles


def get_page_text(title: str) -> Optional[str]:
    data = _wiki_get({
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": "true",
    })
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid == "-1":
            return None
        return page.get("extract", "")
    return None


def is_hanoi_related(text: str, title: str = "") -> bool:
    combined = f"{title} {text[:2000]}"
    return any(kw in combined for kw in HANOI_KEYWORDS)


# ============================================================================ #
#  BƯỚC 1a: SCRAPE LANDMARKS
# ============================================================================ #

def scrape_landmarks(out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_titles = set()
    for title in EXTRA_LANDMARK_PAGES:
        all_titles.add(title)

    print("=" * 60)
    print("BƯỚC 1a: Cào di tích Hà Nội từ Wikipedia")
    print("=" * 60)

    for cat in WIKI_CATEGORIES:
        try:
            members = get_category_members(cat)
            for t in members:
                all_titles.add(t.replace(" ", "_"))
            print(f"  [category] {cat}: {len(members)} bài")
        except Exception as e:
            print(f"  [category] {cat}: LỖI - {e}")
        time.sleep(0.3)

    print(f"\n  Tổng: {len(all_titles)} bài (sau dedup)")
    print("-" * 60)

    saved, skipped_short, skipped_nohanoi, skipped_error = 0, 0, 0, 0
    extra_set = set(EXTRA_LANDMARK_PAGES)

    for i, title in enumerate(sorted(all_titles)):
        slug = re.sub(r"[^\w\-]", "_", title)
        path = out / f"{slug}.json"

        if path.exists():
            saved += 1
            continue

        try:
            text = get_page_text(title.replace("_", " "))
        except Exception as e:
            print(f"  [{i:3d}] {title}: LỖI - {e}")
            skipped_error += 1
            time.sleep(1)
            continue

        if not text or len(text) < 200:
            skipped_short += 1
            continue

        if title not in extra_set and not is_hanoi_related(text, title):
            print(f"  [{i:3d}] {title}: bỏ qua (không Hà Nội)")
            skipped_nohanoi += 1
            continue

        rec = {
            "title": title.replace("_", " "),
            "slug": slug,
            "text": text,
            "source": f"https://vi.wikipedia.org/wiki/{title}",
            "char_count": len(text),
        }
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        saved += 1
        print(f"  [{i:3d}] {title}: {len(text):,} chars ✓")
        time.sleep(0.5)

    print("-" * 60)
    print(f"  Đã lưu:             {saved}")
    print(f"  Bỏ (quá ngắn):      {skipped_short}")
    print(f"  Bỏ (không Hà Nội):  {skipped_nohanoi}")
    print(f"  Lỗi:                {skipped_error}")
    print(f"  Output: {out}")


# ============================================================================ #
#  BƯỚC 1b: SCRAPE FOOD
# ============================================================================ #

def scrape_food(out_dir: str, csv_path: str = None):
    out = Path(out_dir)
    (out / "restaurants").mkdir(parents=True, exist_ok=True)
    (out / "dishes").mkdir(parents=True, exist_ok=True)
    (out / "districts").mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("BƯỚC 1b: Sinh dữ liệu ẩm thực Hà Nội")
    print("=" * 60)

    # --- Đọc CSV ---
    if csv_path and Path(csv_path).exists():
        csv_text = Path(csv_path).read_text(encoding="utf-8")
        print(f"  Đọc CSV: {csv_path}")
    else:
        csv_text = FOOD_CSV.strip()
        print("  Dùng dữ liệu inline")

    reader = csv.DictReader(io.StringIO(csv_text))
    restaurants = list(reader)

    # --- Restaurants ---
    print(f"\n  --- Restaurants: {len(restaurants)} quán ---")
    dish_names_used = set()

    for row in restaurants:
        name = row["tên_quán"].strip()
        slug = re.sub(r"[^\w\-]", "_", name)

        triplets = [
            {"head": name, "relation": "loại_món",
             "tail": row["loại_món"].strip()},
            {"head": name, "relation": "tọa_lạc",
             "tail": row["quận"].strip()},
            {"head": name, "relation": "địa_chỉ",
             "tail": row["địa_chỉ"].strip()},
            {"head": name, "relation": "giá_trung_bình",
             "tail": row["giá_trung_bình"].strip() + "đ"},
        ]

        if row.get("giờ_mở_cửa", "").strip():
            triplets.append({"head": name, "relation": "giờ_mở_cửa",
                             "tail": row["giờ_mở_cửa"].strip()})
        if row.get("nổi_tiếng_vì", "").strip():
            triplets.append({"head": name, "relation": "nổi_tiếng_vì",
                             "tail": row["nổi_tiếng_vì"].strip()})

        landmark = row.get("di_tích_gần_nhất", "").strip()
        distance = row.get("khoảng_cách_km", "").strip()
        if landmark:
            triplets.append({"head": name, "relation": "gần", "tail": landmark})
        if landmark and distance:
            triplets.append({"head": name, "relation": "khoảng_cách",
                             "tail": f"{distance}km từ {landmark}"})

        result = {"title": name, "slug": slug, "type": "Restaurant",
                  "triplets": triplets}
        (out / "restaurants" / f"{slug}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    {name}: {len(triplets)} triplets ✓")
        dish_names_used.add(row["loại_món"].strip())

    # --- Dishes ---
    print(f"\n  --- Dishes: {len(DISH_INFO)} loại món ---")
    for dish_name, info in DISH_INFO.items():
        slug = re.sub(r"[^\w\-]", "_", dish_name)
        triplets = [
            {"head": dish_name, "relation": "mô_tả", "tail": info["mô_tả"]},
            {"head": dish_name, "relation": "nguồn_gốc", "tail": info["nguồn_gốc"]},
            {"head": dish_name, "relation": "đặc_trưng", "tail": info["đặc_trưng"]},
        ]
        result = {"title": dish_name, "slug": slug, "type": "Dish",
                  "triplets": triplets}
        (out / "dishes" / f"{slug}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    {dish_name} ✓")

    missing = dish_names_used - set(DISH_INFO.keys())
    if missing:
        print(f"\n  ⚠ Món trong CSV chưa có DISH_INFO: {missing}")

    # --- Districts (bridge nodes) ---
    print(f"\n  --- Districts: {len(HANOI_DISTRICTS)} quận/huyện ---")
    for district, desc in HANOI_DISTRICTS.items():
        slug = re.sub(r"[^\w\-]", "_", district)
        triplets = [
            {"head": district, "relation": "mô_tả", "tail": desc},
            {"head": district, "relation": "thuộc_thành_phố", "tail": "Hà Nội"},
        ]
        result = {"title": district, "slug": slug, "type": "Location",
                  "triplets": triplets}
        (out / "districts" / f"{slug}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    {district} ✓")

    # --- Summary ---
    n_r = len(list((out / "restaurants").glob("*.json")))
    n_d = len(list((out / "dishes").glob("*.json")))
    n_l = len(list((out / "districts").glob("*.json")))
    print("-" * 60)
    print(f"  Restaurants: {n_r}  |  Dishes: {n_d}  |  Districts: {n_l}")
    print(f"  Output: {out}")


# ============================================================================ #
#  STATS
# ============================================================================ #

def print_stats(landmarks_dir: str = None, food_dir: str = None):
    print("=" * 60)
    print("THỐNG KÊ DỮ LIỆU")
    print("=" * 60)

    if landmarks_dir and Path(landmarks_dir).exists():
        files = list(Path(landmarks_dir).glob("*.json"))
        total_chars = 0
        ranked = []
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            cc = data.get("char_count", len(data.get("text", "")))
            total_chars += cc
            ranked.append((data.get("title", f.stem), cc))
        ranked.sort(key=lambda x: x[1], reverse=True)

        print(f"\n  LANDMARKS (Wikipedia):")
        print(f"    Số bài:        {len(files)}")
        print(f"    Tổng ký tự:    {total_chars:,}")
        print(f"    TB/bài:        {total_chars // max(len(files), 1):,}")
        print(f"    Top 5 dài nhất:")
        for title, cc in ranked[:5]:
            print(f"      {title}: {cc:,} chars")

    if food_dir and Path(food_dir).exists():
        n_r = len(list((Path(food_dir) / "restaurants").glob("*.json")))
        n_d = len(list((Path(food_dir) / "dishes").glob("*.json")))
        n_l = len(list((Path(food_dir) / "districts").glob("*.json")))
        total_t = 0
        for sub in ["restaurants", "dishes", "districts"]:
            for f in (Path(food_dir) / sub).glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                total_t += len(data.get("triplets", []))
        print(f"\n  FOOD (curated):")
        print(f"    Restaurants:   {n_r}")
        print(f"    Dishes:        {n_d}")
        print(f"    Districts:     {n_l}")
        print(f"    Tổng triplets: {total_t}")

    if landmarks_dir and food_dir:
        nl = len(list(Path(landmarks_dir).glob("*.json"))) if Path(landmarks_dir).exists() else 0
        nr = len(list((Path(food_dir) / "restaurants").glob("*.json"))) if (Path(food_dir) / "restaurants").exists() else 0
        nd = len(list((Path(food_dir) / "dishes").glob("*.json"))) if (Path(food_dir) / "dishes").exists() else 0
        ndi = len(list((Path(food_dir) / "districts").glob("*.json"))) if (Path(food_dir) / "districts").exists() else 0
        est_nodes = (nl * 15) + nr + nd + ndi
        est_edges = (nl * 12) + (nr * 6) + (nd * 3)
        print(f"\n  ƯỚC TÍNH KG:")
        print(f"    ~{est_nodes} nodes  |  ~{est_edges} edges")


# ============================================================================ #
#  CLI
# ============================================================================ #

def main():
    ap = argparse.ArgumentParser(description="KG Hà Nội — Bước 1: Thu thập dữ liệu")
    sub = ap.add_subparsers(dest="cmd")

    p1 = sub.add_parser("scrape-landmarks", help="Cào di tích từ Wikipedia")
    p1.add_argument("--out", default="data/wiki_raw")

    p2 = sub.add_parser("scrape-food", help="Sinh dữ liệu ẩm thực")
    p2.add_argument("--csv", default=None, help="File CSV (default: inline)")
    p2.add_argument("--out", default="data/food_raw")

    p3 = sub.add_parser("stats", help="Thống kê dữ liệu")
    p3.add_argument("--landmarks", default="data/wiki_raw")
    p3.add_argument("--food", default="data/food_raw")

    args = ap.parse_args()
    if args.cmd == "scrape-landmarks":
        scrape_landmarks(args.out)
    elif args.cmd == "scrape-food":
        scrape_food(args.out, csv_path=args.csv)
    elif args.cmd == "stats":
        print_stats(args.landmarks, args.food)
    else:
        ap.print_help()
        print("\nChạy trên Kaggle:")
        print("  !python kg_scrape.py scrape-landmarks --out /kaggle/working/wiki_raw/")
        print("  !python kg_scrape.py scrape-food --out /kaggle/working/food_raw/")
        print("  !python kg_scrape.py stats --landmarks /kaggle/working/wiki_raw/ --food /kaggle/working/food_raw/")


if __name__ == "__main__":
    main()
