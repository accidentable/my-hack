"""Generate a placeholder Vietnamese **auto-loan** card-news PNG for the demo.

위반 3종을 의도적으로 심어둠 (data/regulations/README.md 데모 시나리오):
  1. 일 단위 금리 표시      → 금소법-제22조-대출성상품-광고
  2. 100% 승인 단정·과장    → 금소법-제21조-부당권유금지
  3. 위험·연체·수수료 누락  → 금소법-제19조-설명의무

실제 디자인된 카드가 들어오면 이 파일을 교체. 이 이미지의 글꼴 충실도는
중요하지 않음 — GPT-4o 비전이 새 디자인된 카드를 읽거나, mock 모드에서
fixture가 텍스트를 직접 공급함.

Run:
    python -m scripts.make_dummy_sample
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app import config


_LINES = [
    ("VAY MUA Ô TÔ JB VIỆT NAM", 36),
    ("(JB Vietnam 자동차 대출)", 18),
    ("", 14),
    ("Chỉ 9.900 đồng/ngày !", 32),                # ← 일 단위 금리 표시 (위반 1)
    ("(하루 단 9,900동)", 16),
    ("", 10),
    ("100% chấp thuận — không cần thẩm định", 28),   # ← 단정·과장 (위반 2)
    ("(100% 승인 · 심사 불필요)", 16),
    ("", 10),
    ("Đăng ký ngay hôm nay !", 24),
    ("(오늘 바로 신청)", 14),
    ("", 18),
    # 위반 3: 연체이자율·부수비용·심사 조건 등 중요사항이 *의도적으로* 누락됨.
    # 카드 어디에도 lãi quá hạn / phí trả nợ trước hạn / điều kiện 등이 안 적힘.
    ("(* placeholder loan card — replace with designed sample)", 12),
]


def main() -> int:
    config.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    out_path: Path = config.SAMPLES_DIR / "vi_loan_card_placeholder.png"

    img = Image.new("RGB", (1080, 1080), color=(248, 250, 253))
    draw = ImageDraw.Draw(img)

    y = 100
    for text, size in _LINES:
        draw.text((80, y), text, fill=(20, 30, 60))
        y += size + 22

    img.save(out_path)
    print(f"Wrote placeholder card: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
