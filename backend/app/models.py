# SQLAlchemy 模型：保留原表名、字段名、精度、默认值、索引和外键行为。
"""SQLAlchemy mappings preserving existing MySQL names and precision."""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    FetchedValue,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import CHAR, DATETIME, DECIMAL, MEDIUMBLOB, TEXT, VARCHAR
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow():
    value = datetime.now(UTC).replace(tzinfo=None)
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


class User(Base):
    __tablename__ = "User"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    username = Column(
        VARCHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="登录用户名，唯一",
    )
    passwordHash = Column(
        VARCHAR(255, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="登录密码的 bcrypt 哈希，不存储明文",
    )
    role = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        default="user",
        server_default=text("'user'"),
        comment="系统权限：admin、user 或 readonly；管理员不能查看其他用户财务数据",
    )
    banned = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="封禁后禁止登录和使用已有会话、MCP 授权",
    )
    mustChangePassword = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="首次登录必须设置新的强密码",
    )
    baseCurrency = Column(
        CHAR(3, collation="utf8mb4_unicode_ci"),
        nullable=False,
        default="CNY",
        server_default=text("'CNY'"),
        comment="本位币代码",
    )
    hiddenMenus = Column(
        VARCHAR(128, collation="utf8mb4_unicode_ci"),
        nullable=False,
        default="",
        server_default=text("''"),
        comment="隐藏菜单标识列表",
    )
    sessionHours = Column(
        Integer,
        nullable=False,
        default=168,
        server_default=text("168"),
        comment="登录有效时长（小时），范围 1 至 720",
    )
    requireHiddenPassword = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="查看隐藏项目是否需要再次验证密码",
    )
    overviewCards = Column(
        JSON, nullable=True, comment="总览显示的卡片键列表，NULL 表示默认全部显示"
    )
    includeIndependentAssets = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="独立资产是否参与资产总览和净资产轨迹",
    )
    accountGroupOrder = Column(
        JSON, nullable=True, comment="账户分组显示顺序；空值表示沿用默认顺序"
    )
    showNotes = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="是否显示备注",
    )
    idleMinutes = Column(
        Integer,
        nullable=False,
        default=30,
        server_default=text("30"),
        comment="无操作退出分钟数，0 表示关闭",
    )
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="记录创建时间，UTC",
    )
    updatedAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="记录更新时间，UTC",
    )
    __table_args__ = (
        UniqueConstraint("username", name="User_username_key"),
        {"comment": "用户及个人设置"},
    )


class AgentCall(Base):
    __tablename__ = "AgentCall"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="审计标识",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    grantId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="调用所属连接标识",
    )
    tool = Column(
        VARCHAR(100, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="调用的工具名称",
    )
    status = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="结果状态：success 或 error",
    )
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="调用完成时间，UTC",
    )
    __table_args__ = (
        Index("AgentCall_userId_createdAt_idx", "userId", "createdAt"),
        {"comment": "MCP 调用审计，不保存参数、密码、令牌或财务内容"},
    )


class AgentClient(Base):
    __tablename__ = "AgentClient"
    __table_args__: ClassVar[dict] = {"comment": "OAuth 动态注册客户端元数据"}
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        comment="唯一标识",
    )
    metadata_ = Column(
        "metadata", JSON, nullable=False, comment="公开客户端注册元数据，不保存用户凭据"
    )
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="创建时间，UTC",
    )


class AgentAuthorization(Base):
    __tablename__ = "AgentAuthorization"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        comment="所属用户标识，用于数据隔离",
    )
    clientId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="OAuth 客户端标识；个人令牌为空",
    )
    parameters = Column(
        JSON, nullable=False, comment="具体操作参数；禁止保存密码及令牌"
    )
    codeDigest = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="一次性授权码 SHA-256 摘要",
    )
    expiresAt = Column(DATETIME(fsp=3), nullable=False, comment="到期时间，UTC")
    status = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="当前处理状态",
    )
    __table_args__ = (
        UniqueConstraint("codeDigest", name="AgentAuthorization_codeDigest_key"),
        {"comment": "短期 OAuth 授权请求及一次性授权码摘要"},
    )


class AgentGrant(Base):
    __tablename__ = "AgentGrant"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    clientId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="OAuth 客户端标识；个人令牌为空",
    )
    name = Column(
        VARCHAR(100, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="用户可见连接名称",
    )
    scopes = Column(
        JSON,
        nullable=False,
        comment="权限列表：read、draft 或 write；隐藏账户附加权限 hidden_read、hidden_write",
    )
    resource = Column(
        VARCHAR(500, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="令牌适用的规范 MCP 资源地址",
    )
    accessDigest = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="访问令牌 SHA-256 摘要；完整值仅颁发时返回",
    )
    refreshDigest = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="刷新令牌 SHA-256 摘要，使用后轮换",
    )
    expiresAt = Column(
        DATETIME(fsp=3),
        nullable=True,
        comment="访问令牌到期时间，UTC；空表示可撤销的永久个人令牌",
    )
    refreshExpiresAt = Column(
        DATETIME(fsp=3),
        nullable=True,
        comment="刷新授权到期时间，UTC；空表示永久 OAuth 授权或个人令牌不适用",
    )
    revokedAt = Column(
        DATETIME(fsp=3), nullable=True, comment="撤销时间，UTC；空表示未撤销"
    )
    sessionId = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="本连接的独立业务授权会话标识，不作为 MCP 凭证",
    )
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="创建时间，UTC",
    )
    __table_args__ = (
        UniqueConstraint("accessDigest", name="AgentGrant_accessDigest_key"),
        UniqueConstraint("refreshDigest", name="AgentGrant_refreshDigest_key"),
        Index("AgentGrant_userId_createdAt_idx", "userId", "createdAt"),
        {"comment": "用户授权连接、令牌摘要及资源权限"},
    )


class AgentOperation(Base):
    __tablename__ = "AgentOperation"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    grantId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="发起操作的授权连接标识",
    )
    key = Column(
        VARCHAR(128, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="同用户唯一的客户端幂等键",
    )
    hash = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="工具和参数的规范摘要；拒绝同键不同参数",
    )
    tool = Column(
        VARCHAR(100, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="业务工具名称",
    )
    parameters = Column(
        JSON, nullable=False, comment="具体操作参数；禁止保存密码及令牌"
    )
    snapshot = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="确认前的账目版本摘要，防止覆盖并发修改",
    )
    status = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="当前处理状态",
    )
    expiresAt = Column(DATETIME(fsp=3), nullable=False, comment="到期时间，UTC")
    result = Column(JSON, nullable=True, comment="结构化操作结果或最近提交失败原因")
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="创建时间，UTC",
    )
    completedAt = Column(DATETIME(fsp=3), nullable=True, comment="完成或取消时间，UTC")
    __table_args__ = (
        UniqueConstraint("userId", "key", name="AgentOperation_userId_key_key"),
        Index("AgentOperation_userId_createdAt_idx", "userId", "createdAt"),
        {"comment": "Agent 写入草稿、幂等记录及提交结果"},
    )


class Session(Base):
    __tablename__ = "Session"
    id = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        comment="随机会话令牌的 SHA-256 摘要",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    expiresAt = Column(DATETIME(fsp=3), nullable=False, comment="会话过期时间，UTC")
    lastActivity = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="最后有效交互时间，UTC",
    )
    revealUntil = Column(
        DATETIME(fsp=3),
        nullable=True,
        comment="隐藏项目授权截止时间，UTC；空表示未解锁",
    )
    backupDigest = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="已下载备份内容的 SHA-256 摘要",
    )
    backupExpiresAt = Column(
        DATETIME(fsp=3), nullable=True, comment="备份清空确认凭据截止时间，UTC"
    )
    __table_args__ = (
        Index("Session_userId_idx", "userId"),
        {"comment": "登录会话与隐藏项目查看授权"},
    )


class Position(Base):
    __tablename__ = "Position"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    importedFromId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="备份导入来源项目标识，用于重复导入识别",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    kind = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="项目类型：account 账户、asset 独立资产、debt 债务",
    )
    side = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="统计方向：asset 资产或借出应收、liability 负债或借入应付",
    )
    name = Column(
        VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False, comment="显示名称"
    )
    category = Column(
        VARCHAR(40, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="项目分类代码",
    )
    groupName = Column(
        VARCHAR(60, collation="utf8mb4_unicode_ci"),
        nullable=False,
        default="",
        server_default=text("''"),
        comment="自定义账户分组",
    )
    currency = Column(
        CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False, comment="原始币种代码"
    )
    notes = Column(
        TEXT(collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="用户备注，原文保留",
    )
    archived = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="是否归档；归档项目仍计入总额",
    )
    hidden = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="是否隐藏；未解锁时不参与可见范围统计",
    )
    included = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="是否参与资产负债总额及净资产轨迹",
    )
    lastRepaymentMonth = Column(
        CHAR(7, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="最后手动标记已完成还款的业务月份，UTC+8 YYYY-MM；空表示未标记",
    )
    lastBookedDate = Column(
        CHAR(10, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="最后手动标记已完成记账的业务日期，UTC+8 YYYY-MM-DD；空表示未标记",
    )
    metalType = Column(
        VARCHAR(12, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="贵金属品种：gold 黄金或 silver 白银",
    )
    metalGrams = Column(DECIMAL(24, 8), nullable=True, comment="贵金属总重量，单位克")
    metalPurity = Column(
        DECIMAL(12, 8),
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="贵金属纯度比例，0 至 1",
    )
    metalCostPerGram = Column(
        DECIMAL(24, 12),
        nullable=True,
        comment="买入时每克实物成本，原币；空值表示不计算盈亏",
    )
    autoValuation = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="是否随每日价格更新自动记录估值",
    )
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="记录创建时间，UTC",
    )
    updatedAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="记录更新时间，UTC",
    )
    iconId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("Icon.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="关联账户图标标识",
    )
    __table_args__ = (
        Index("Position_userId_kind_idx", "userId", "kind"),
        UniqueConstraint(
            "userId", "importedFromId", name="Position_userId_importedFromId_key"
        ),
        {"comment": "持有项目：账户、独立资产和借入借出债务"},
    )


class Revision(Base):
    __tablename__ = "Revision"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    sequence = Column(
        Integer,
        nullable=False,
        server_default=FetchedValue(),
        comment="数据库自增唯一顺序，同业务时间按此排序",
    )
    positionId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("Position.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属持有项目标识",
    )
    amount = Column(
        DECIMAL(24, 8),
        nullable=False,
        comment="变更后的原币绝对余额，不是收支增量，禁止对全部历史求和",
    )
    effectiveDate = Column(
        DATETIME(fsp=3),
        nullable=False,
        comment="北京时间业务时间对应的 UTC，精确到分钟",
    )
    notes = Column(
        TEXT(collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="用户备注，原文保留",
    )
    reason = Column(
        VARCHAR(20, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="变更原因：初始、余额、估值、转账或借贷配对操作",
    )
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="记录创建时间，UTC",
    )
    updatedAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="记录更新时间，UTC",
    )
    __table_args__ = (
        UniqueConstraint("sequence", name="Revision_sequence_key"),
        Index(
            "Revision_positionId_effectiveDate_sequence_idx",
            "positionId",
            "effectiveDate",
            "sequence",
        ),
        Index(
            "Revision_positionId_reason_effectiveDate_sequence_idx",
            "positionId",
            "reason",
            "effectiveDate",
            "sequence",
        ),
        {"comment": "余额历史：金额为变更后的绝对余额"},
    )


class PositionLink(Base):
    __tablename__ = "PositionLink"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    sourceId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("Position.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="关联来源项目标识，通常为债务",
    )
    targetId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("Position.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="关联目标项目标识，通常为账户或资产",
    )
    __table_args__ = (
        UniqueConstraint(
            "sourceId", "targetId", name="PositionLink_sourceId_targetId_key"
        ),
        {"comment": "项目关联关系，不参与金额求和"},
    )


class ExchangeRate(Base):
    __tablename__ = "ExchangeRate"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    currency = Column(
        CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False, comment="原始币种代码"
    )
    baseCurrency = Column(
        CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False, comment="本位币代码"
    )
    date = Column(Date, nullable=False, comment="汇率业务日期")
    rate = Column(DECIMAL(24, 12), nullable=False, comment="每单位原币对应的本位币金额")
    source = Column(
        VARCHAR(30, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="汇率来源标识，保留已有历史来源",
    )
    __table_args__ = (
        UniqueConstraint(
            "userId",
            "currency",
            "baseCurrency",
            "date",
            name="ExchangeRate_userId_currency_baseCurrency_date_key",
        ),
        {"comment": "用户原币兑本位币的历史汇率"},
    )


class Icon(Base):
    __tablename__ = "Icon"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    ownerId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="上传用户标识；空可表示系统图标或原用户已删除",
    )
    name = Column(
        VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False, comment="显示名称"
    )
    shared = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="是否公开共享给已登录用户",
    )
    # 共享图标软删除仅下架，保留图片和既有账户引用。
    deletedAt = Column(DATETIME(fsp=3), nullable=True, comment="共享图标下架时间，UTC")
    hash = Column(
        CHAR(64, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="规范化图标内容的 SHA-256 摘要",
    )
    data = Column(MEDIUMBLOB, nullable=False, comment="规范化静态 PNG 图片二进制")
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="记录创建时间，UTC",
    )
    __table_args__ = (
        UniqueConstraint(
            "ownerId", "hash", "shared", name="Icon_ownerId_hash_shared_key"
        ),
        Index("Icon_shared_name_idx", "shared", "name"),
        Index("Icon_shared_deletedAt_name_idx", "shared", "deletedAt", "name"),
        {"comment": "可复用账户图标"},
    )


class Transfer(Base):
    __tablename__ = "Transfer"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    importedFromId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="备份导入来源项目标识，用于重复导入识别",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    sourceId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("Position.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="来源资产账户标识",
    )
    targetId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("Position.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="目标账户或债务标识",
    )
    sourceRevisionId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="来源账户配对余额历史标识",
    )
    targetRevisionId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="目标项目配对余额历史标识",
    )
    sourceCurrency = Column(
        CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False, comment="来源账户币种"
    )
    targetCurrency = Column(
        CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False, comment="目标项目币种"
    )
    amount = Column(
        DECIMAL(24, 8), nullable=False, comment="本次来源账户本金金额，不是变更后余额"
    )
    received = Column(
        DECIMAL(24, 8), nullable=False, comment="本次目标到账金额或债务本金金额"
    )
    fee = Column(DECIMAL(24, 8), nullable=False, comment="来源币种手续费；负数表示优惠")
    effectiveDate = Column(
        DATETIME(fsp=3),
        nullable=False,
        comment="北京时间业务时间对应的 UTC，精确到分钟",
    )
    notes = Column(
        TEXT(collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="用户备注，原文保留",
    )
    operation = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        default="transfer",
        server_default=text("'transfer'"),
        comment="操作类型：transfer 转账、borrow 借入、lend 借出、collect 收款、repay 还款",
    )
    createdAt = Column(
        DATETIME(fsp=3),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="记录创建时间，UTC",
    )
    __table_args__ = (
        UniqueConstraint("sourceRevisionId", name="Transfer_sourceRevisionId_key"),
        UniqueConstraint("targetRevisionId", name="Transfer_targetRevisionId_key"),
        UniqueConstraint(
            "userId", "importedFromId", name="Transfer_userId_importedFromId_key"
        ),
        Index("Transfer_userId_effectiveDate_id_idx", "userId", "effectiveDate", "id"),
        {"comment": "资金往来及账户与债务的双边配对记账"},
    )


class Schedule(Base):
    __tablename__ = "Schedule"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    importedFromId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="备份来源计划标识，用于重复导入识别",
    )
    name = Column(
        VARCHAR(100, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="计划显示名称",
    )
    operation = Column(
        VARCHAR(16, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="操作类型：expense 支出或 transfer 转账",
    )
    sourceId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="支出或转出资产账户标识",
    )
    targetId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        nullable=True,
        comment="转入账户标识；支出计划为空",
    )
    amount = Column(DECIMAL(24, 8), nullable=False, comment="原币支出或转出金额")
    received = Column(
        DECIMAL(24, 8), nullable=False, comment="原币到账金额；支出计划为零"
    )
    nextAt = Column(
        DATETIME(fsp=3), nullable=False, comment="下次到期业务时间对应的 UTC"
    )
    intervalDays = Column(
        Integer, nullable=False, comment="重复间隔天数；零表示仅执行一次"
    )
    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="是否启用计划",
    )
    completed = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="一次性计划是否已执行完毕",
    )
    notes = Column(
        TEXT(collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="用户备注，原文保留",
    )
    __table_args__ = (
        Index("Schedule_userId_enabled_nextAt_idx", "userId", "enabled", "nextAt"),
        UniqueConstraint(
            "userId", "importedFromId", name="Schedule_userId_importedFromId_key"
        ),
        {"comment": "按需执行的定时支出或转账计划"},
    )


class MetalPrice(Base):
    __tablename__ = "MetalPrice"
    id = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid4()),
        comment="唯一标识",
    )
    userId = Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="所属用户标识，用于数据隔离",
    )
    metalType = Column(
        VARCHAR(12, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="品种：gold 黄金或 silver 白银",
    )
    currency = Column(
        CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False, comment="价格币种"
    )
    price = Column(DECIMAL(24, 12), nullable=False, comment="纯金属每克价格")
    date = Column(Date, nullable=False, comment="报价日期，UTC+8 自然日")
    source = Column(
        VARCHAR(20, collation="utf8mb4_unicode_ci"),
        nullable=False,
        comment="价格来源：manual 或 goldapi",
    )
    quotedAt = Column(DATETIME(fsp=3), nullable=False, comment="报价对应时间，UTC")
    __table_args__ = (
        UniqueConstraint(
            "userId",
            "metalType",
            "currency",
            "date",
            name="MetalPrice_userId_metalType_currency_date_key",
        ),
        {"comment": "用户的贵金属每克参考价历史"},
    )
