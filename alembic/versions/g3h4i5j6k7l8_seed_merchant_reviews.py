"""seed mock merchant reviews for AI Review Summarizer demo

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-05-08 14:10:00.000000

Seeds realistic Vietnamese food delivery reviews for 3 merchants:
  - Saigon Pho House (20000000-0000-0000-0000-000000000001)
  - Banh Mi 88       (20000000-0000-0000-0000-000000000002)
  - Com Tam District 1 (20000000-0000-0000-0000-000000000003)
"""

from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g3h4i5j6k7l8"
down_revision: Union[str, None] = "f2g3h4i5j6k7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Merchant IDs — must match c9e0f1a2b3c4 seed
# ---------------------------------------------------------------------------
MERCHANT_PHO = "20000000-0000-0000-0000-000000000001"
MERCHANT_BANHMI = "20000000-0000-0000-0000-000000000002"
MERCHANT_COMTAM = "20000000-0000-0000-0000-000000000003"

# Fake reviewer user IDs (non-merchant users)
REVIEWER_IDS = [f"50000000-0000-0000-0000-0000000000{str(i).zfill(2)}" for i in range(1, 16)]

_now = datetime.now(timezone.utc)


def _ts(days_ago: int) -> datetime:
    return _now - timedelta(days=days_ago)


def _row(
    rid: str,
    merchant_id: str,
    user_idx: int,
    rating: int,
    comment: str,
    reviewer_name: str,
    days_ago: int,
    reply: str | None = None,
) -> dict:
    return {
        "id": rid,
        "merchant_id": merchant_id,
        "user_id": REVIEWER_IDS[user_idx],
        "order_id": None,
        "rating": rating,
        "comment": comment,
        "reply": reply,
        "reviewer_name": reviewer_name,
        "reviewer_avatar": None,
        "created_at": _ts(days_ago),
        "updated_at": _ts(days_ago),
        "is_deleted": False,
        "deleted_at": None,
    }


REVIEWS = [
    # =========================================================================
    # Saigon Pho House — mix of 4★ and 5★, 1 complaint about condiments
    # =========================================================================
    _row("rv-ph-01", MERCHANT_PHO, 0, 5,
         "Phở bò tái ở đây cực ngon! Nước dùng trong, vị thanh mà vẫn đậm đà, thịt bò tươi và nhiều. "
         "Giao hàng nhanh hơn dự kiến. Sẽ order lại.",
         "Minh Tuấn", 2),
    _row("rv-ph-02", MERCHANT_PHO, 1, 5,
         "Best pho in District 1 hands down. The broth is so clean and rich at the same time. "
         "Very generous portion of beef. Highly recommend the Pho Bo Tai.",
         "David K.", 5),
    _row("rv-ph-03", MERCHANT_PHO, 2, 4,
         "Nước dùng ngon, nhưng lần này thiếu tương ớt và tương đen. "
         "Phải tự bỏ thêm gia vị mà không có. Vẫn ổn nhưng cần cải thiện.",
         "Lan Phương", 7,
         reply="Cảm ơn bạn đã phản hồi! Chúng tôi sẽ chú ý kèm đủ gia vị hơn."),
    _row("rv-ph-04", MERCHANT_PHO, 3, 5,
         "Phở chuẩn vị Nam, ăn một lần là ghiền. Giao hàng nhanh, đóng gói cẩn thận. "
         "Thịt bò tái vừa chín tới khi giao đến, không bị quá chín.",
         "Hồng Nhung", 10),
    _row("rv-ph-05", MERCHANT_PHO, 4, 3,
         "Hôm nay order bị trễ 20 phút so với dự kiến. Phở nguội một chút. "
         "Chất lượng đồ ăn ổn nhưng giao hàng cần cải thiện.",
         "Quốc Bảo", 12),
    _row("rv-ph-06", MERCHANT_PHO, 5, 5,
         "Tô phở đẹp, thịt nhiều, bánh phở mềm không bị nát. Nước dùng thơm mùi hoa hồi. "
         "Giá cả hợp lý so với chất lượng. Nhân viên hỗ trợ nhiệt tình.",
         "Bích Thảo", 15),
    _row("rv-ph-07", MERCHANT_PHO, 6, 4,
         "Good pho, authentic flavors. The beef slices could be a bit thicker but overall very good. "
         "Will order again for sure.",
         "Sarah M.", 18),
    _row("rv-ph-08", MERCHANT_PHO, 7, 4,
         "Nước dùng ngon nhưng giá hơi cao hơn mặt bằng chung. Khoảng 85k/tô là hơi đắt. "
         "Chất lượng bù đắp được nhưng vẫn muốn rẻ hơn chút.",
         "Văn Đức", 20),
    _row("rv-ph-09", MERCHANT_PHO, 8, 5,
         "Phở đây ăn như phở nhà nấu, không bị vị công nghiệp. Thịt bò Úc chất lượng. "
         "Recommend bạn thêm giò heo vào, ngon lắm!",
         "Thanh Mai", 25),
    _row("rv-ph-10", MERCHANT_PHO, 9, 2,
         "Lần này không hài lòng. Thiếu tương đen và tương ớt. Thịt ít hơn mọi khi. "
         "Hy vọng quán chú ý hơn vào kiểm soát chất lượng.",
         "Minh Khoa", 30),

    # =========================================================================
    # Banh Mi 88 — mostly 5★, praised for crispy bread & fillings
    # =========================================================================
    _row("rv-bm-01", MERCHANT_BANHMI, 0, 5,
         "Bánh mì giòn tan, nhân nhiều và đầy đủ. Chả lụa thơm, pate béo ngậy. "
         "Giao hàng siêu nhanh, bánh vẫn còn giòn khi nhận.",
         "Thu Hà", 1),
    _row("rv-bm-02", MERCHANT_BANHMI, 1, 5,
         "Best banh mi I've had delivered! The bread is still crispy even after 30min of delivery. "
         "The pickled veggies are perfectly tangy. Will definitely reorder.",
         "John T.", 3),
    _row("rv-bm-03", MERCHANT_BANHMI, 2, 5,
         "Bánh mì thịt nướng số 1! Thịt nướng thơm lừng, không bị khô. "
         "Rau cải giòn tươi. Giá 45k cho một ổ bánh này là hợp lý lắm.",
         "Ngọc Ánh", 6),
    _row("rv-bm-04", MERCHANT_BANHMI, 3, 4,
         "Rất ngon nhưng lần này đồ dưa cải ít hơn bình thường. "
         "Mong quán cho đồ dưa nhiều hơn một chút vì đó là điểm cộng của bánh mì này.",
         "Duy Hùng", 8,
         reply="Cảm ơn bạn! Chúng tôi sẽ đảm bảo lượng dưa cải đồng đều hơn."),
    _row("rv-bm-05", MERCHANT_BANHMI, 4, 5,
         "Bánh mì gà xả rất khác biệt và ngon. Vị sả thơm rất đặc trưng. "
         "Đóng gói cẩn thận, bánh không bị nát dù giao xa.",
         "Phương Thảo", 11),
    _row("rv-bm-06", MERCHANT_BANHMI, 5, 3,
         "Hôm nay order bị nhầm món. Nhận được bánh mì chay trong khi đặt thịt nướng. "
         "Phải chờ đổi khá lâu. Mong quán kiểm tra kỹ hơn.",
         "Trung Kiên", 14),
    _row("rv-bm-07", MERCHANT_BANHMI, 6, 5,
         "Giòn, ngon, rẻ! Chuẩn bánh mì Sài Gòn authentic. "
         "Ăn buổi sáng thay phở đổi vị rất hay. Sẽ quay lại mỗi tuần.",
         "Khánh Linh", 17),
    _row("rv-bm-08", MERCHANT_BANHMI, 7, 5,
         "The char siu pork banh mi is incredible. Perfectly marinated and grilled. "
         "The mayo they use is homemade style, much better than regular brands.",
         "Emma W.", 22),

    # =========================================================================
    # Com Tam District 1 — high satisfaction, portion size praised
    # =========================================================================
    _row("rv-ct-01", MERCHANT_COMTAM, 0, 5,
         "Cơm tấm sườn bì chả cực ngon! Sườn nướng mềm, thơm lừng. "
         "Phần ăn nhiều, ăn no bụng mà giá chỉ 65k. Nước mắm pha chuẩn vị.",
         "Minh Tú", 2),
    _row("rv-ct-02", MERCHANT_COMTAM, 1, 4,
         "Cơm ngon, thịt nhiều nhưng bì hơi cứng lần này. "
         "Mong quán để bì mềm hơn. Ngoài ra rất ổn.",
         "Xuân Hoa", 5),
    _row("rv-ct-03", MERCHANT_COMTAM, 2, 5,
         "Best com tam in District 1! The broken rice texture is perfect. "
         "The grilled pork chop is very tender and flavorful. Great value for money.",
         "Mike L.", 8),
    _row("rv-ct-04", MERCHANT_COMTAM, 3, 5,
         "Cơm tấm đây ăn như ở nhà, rất authentic. Sườn non mềm tan trong miệng. "
         "Giao hàng còn nóng hổi. Sẽ recommend cho bạn bè.",
         "Hải Yến", 10),
    _row("rv-ct-05", MERCHANT_COMTAM, 4, 4,
         "Rất ngon nhưng giao hơi trễ 15 phút. Cơm có nguội chút nhưng vẫn ăn được. "
         "Phần ăn rất nhiều và đầy đủ topping.",
         "Tuấn Anh", 13),
    _row("rv-ct-06", MERCHANT_COMTAM, 5, 5,
         "Cơm tấm sườn trứng hấp dẫn lắm. Trứng ốp la lòng đào vừa đẹp. "
         "Bì trộn đều gia vị. Giá hợp lý, phục vụ nhanh.",
         "Diệu Linh", 16),
    _row("rv-ct-07", MERCHANT_COMTAM, 6, 3,
         "Giá hơi cao so với các quán cơm tấm khác trong khu vực. "
         "Chất lượng ổn nhưng không đáng tiền lắm so với chỗ khác gần đây.",
         "Bảo Long", 19),
    _row("rv-ct-08", MERCHANT_COMTAM, 7, 5,
         "Order lần đầu và rất hài lòng. Sườn nướng không bị khô dù giao hàng. "
         "Cơm dẻo, mềm đúng chuẩn. Nước mắm đặc biệt thơm ngon.",
         "Ngân Hà", 22),
]


def upgrade() -> None:
    reviews_table = sa.table(
        "merchant_reviews",
        sa.column("id", sa.String),
        sa.column("merchant_id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("order_id", sa.String),
        sa.column("rating", sa.Integer),
        sa.column("comment", sa.Text),
        sa.column("reply", sa.Text),
        sa.column("reviewer_name", sa.String),
        sa.column("reviewer_avatar", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("is_deleted", sa.Boolean),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(reviews_table, REVIEWS)


def downgrade() -> None:
    op.execute(
        "DELETE FROM merchant_reviews WHERE id LIKE 'rv-%'"
    )
