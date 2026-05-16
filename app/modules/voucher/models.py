# =============================================================================
# Voucher Module - ORM Models
# =============================================================================

import datetime
from unittest.mock import Base

from click import DateTime
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from transformers import Optional

from app.modules.journey.models import JourneyOffer
from app.modules.user.models import User
class UserVoucher(Base):
    __tablename__ = "user_vouchers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    voucher_id: Mapped[int] = mapped_column(Integer, ForeignKey("vouchers.id"))
    
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True) # type: ignore
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow) # type: ignore
    
    # Relationship
    user: Mapped["User"] = relationship("User")
    voucher: Mapped["voucher"] = relationship("Voucher", back_populates="user_vouchers") # type: ignore
