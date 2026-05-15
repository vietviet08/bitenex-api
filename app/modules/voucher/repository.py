from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.voucher.models import Voucher, UserVoucher
from app.modules.base import BaseRepository


class VoucherRepository(BaseRepository[Voucher]):
    model = Voucher

    async def get_by_code(self, code: str) -> Optional[Voucher]:
        """Lấy voucher theo code"""
        query = select(Voucher).where(
            Voucher.code == code.upper(),
            Voucher.is_active == True
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_voucher(self, user_id: int, voucher_id: int) -> Optional[UserVoucher]:
        """Lấy thông tin voucher của user"""
        query = select(UserVoucher).where(
            UserVoucher.user_id == user_id,
            UserVoucher.voucher_id == voucher_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def increase_usage(self, voucher_id: int, user_id: int):
        """Tăng số lần sử dụng voucher"""
        # Tăng used_count của voucher
        await self.db.execute(
            update(Voucher)
            .where(Voucher.id == voucher_id)
            .values(used_count=Voucher.used_count + 1)
        )

        # Cập nhật hoặc tạo UserVoucher
        user_voucher = await self.get_user_voucher(user_id, voucher_id)
        
        if user_voucher:
            await self.db.execute(
                update(UserVoucher)
                .where(UserVoucher.id == user_voucher.id)
                .values(
                    times_used=UserVoucher.times_used + 1,
                    last_used_at=datetime.utcnow()
                )
            )
        else:
            new_user_voucher = UserVoucher(
                user_id=user_id,
                voucher_id=voucher_id,
                times_used=1,
                last_used_at=datetime.utcnow()
            )
            self.db.add(new_user_voucher)
        
        await self.db.commit()