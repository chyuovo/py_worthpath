# 请求校验：禁止未知字段，金额必须为十进制字符串，避免浮点误差。
"""Strict decimal-string and business-time input contracts."""

from typing import Literal
import re
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from .common import *


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @classmethod
    def parse(cls, body):
        return cls.model_validate(body).model_dump()


def money(v, signed=True, positive=False, scale=8):
    pattern = (
        ("-?" if signed else "")
        + r"(0|[1-9]\d{0,"
        + str(15 if scale == 8 else 11)
        + r"})(\.\d{1,"
        + str(scale)
        + r"})?"
    )
    if not isinstance(v, str) or not re.fullmatch(pattern, v):
        raise ValueError("金额须为十进制字符串")
    if positive and dec(v) <= 0:
        raise ValueError("金额必须大于零")
    return v


def check_date(v, future=False):
    if not isinstance(v, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?", v
    ):
        raise ValueError("业务时间无效或在未来（北京时间）")
    d = business_date(v)
    if v < "1900-01-01" or (not future and d > now()):
        raise ValueError("业务时间无效或在未来（北京时间）")
    return v


class Meta(Input):
    name: str
    category: str
    notes: str = ""
    archived: bool = False
    hidden: bool = False
    included: bool | None = None
    groupName: str | None = None
    iconId: str | None = None

    @field_validator("name", "category", "groupName")
    @classmethod
    def text(cls, v, info):
        if v is None:
            raise ValueError("字段不能为空")
        v = v.strip()
        maximum = {"name": 100, "category": 40, "groupName": 60}[info.field_name]
        if len(v) > maximum or (info.field_name != "groupName" and not v):
            raise ValueError("文本长度无效")
        return v

    @field_validator("included")
    @classmethod
    def included_not_null(cls, v):
        if v is None:
            raise ValueError("字段不能为空")
        return v

    @field_validator("notes")
    @classmethod
    def memo(cls, v):
        if len(v) > 2000:
            raise ValueError("备注最多 2000 字符")
        return v

    @field_validator("iconId")
    @classmethod
    def uuid(cls, v):
        if v is not None:
            UUID(v)
        return v


class PositionInput(Meta):
    kind: Literal["account", "asset", "debt"]
    side: Literal["asset", "liability"]
    currency: Literal[
        "CNY", "USD", "HKD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "SGD"
    ]
    amount: str
    date: str

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, v):
        return money(v)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v):
        return check_date(v)

    @model_validator(mode="after")
    def validate_position(self):
        if self.amount.startswith("-") and self.kind != "account":
            raise ValueError("仅账户支持负余额")
        if (self.kind == "asset" and self.side != "asset") or (
            self.kind == "account"
            and self.category in ("credit_card", "loan")
            and self.side != "liability"
        ):
            raise ValueError("项目类型与资产负债属性不符")
        return self


class RevisionInput(Input):
    amount: str
    date: str
    notes: str = ""
    reason: Literal[
        "initial",
        "scheduled_expense",
        "balance",
        "valuation",
        "repayment",
        "correction",
        "transfer_out",
        "transfer_in",
        "loan_borrow",
        "loan_lend",
        "loan_collect",
        "loan_repay",
    ] = "balance"

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, v):
        return money(v)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v):
        return check_date(v)

    @field_validator("notes")
    @classmethod
    def memo(cls, v):
        return Meta.memo(v)


class TransferInput(Input):
    operation: Literal["transfer", "borrow", "lend", "collect", "repay"] = "transfer"
    requestId: str | None = None
    sourceId: str
    targetId: str
    amount: str
    received: str
    fee: str = "0"
    date: str
    notes: str = ""

    @field_validator("sourceId", "targetId", "requestId")
    @classmethod
    def uuid(cls, v):
        if v is None:
            raise ValueError("UUID 不能为空")
        UUID(v)
        return v

    @field_validator("amount", "received")
    @classmethod
    def positive(cls, v):
        return money(v, signed=False, positive=True)

    @field_validator("fee")
    @classmethod
    def valid_fee(cls, v):
        return money(v)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v):
        return check_date(v)

    @field_validator("notes")
    @classmethod
    def memo(cls, v):
        return Meta.memo(v)

    @model_validator(mode="after")
    def validate_transfer(self):
        if self.sourceId == self.targetId:
            raise ValueError("不能向同一账户转账")
        if -dec(self.fee) > dec(self.amount):
            raise ValueError("手续费优惠不能超过转出金额")
        return self
