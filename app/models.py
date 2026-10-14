"""SQLAlchemy mappings preserving existing MySQL names and precision."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, Integer, Boolean, JSON, Date, ForeignKey, Index, UniqueConstraint, FetchedValue, text
from sqlalchemy.dialects.mysql import CHAR, VARCHAR, DECIMAL, DATETIME, MEDIUMBLOB, TEXT
from sqlalchemy.orm import declarative_base
Base=declarative_base()
def utcnow(): return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = 'User'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    username = Column(VARCHAR(64, collation="utf8mb4_unicode_ci"), nullable=False)
    passwordHash = Column(VARCHAR(255, collation="utf8mb4_unicode_ci"), nullable=False)
    role = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False, default='user', server_default=text("'user'"))
    banned = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    mustChangePassword = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    baseCurrency = Column(CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False, default='CNY', server_default=text("'CNY'"))
    hiddenMenus = Column(VARCHAR(128, collation="utf8mb4_unicode_ci"), nullable=False, default='', server_default=text("''"))
    sessionHours = Column(Integer, nullable=False, default=168, server_default=text('168'))
    requireHiddenPassword = Column(Boolean, nullable=False, default=True, server_default=text('1'))
    overviewCards = Column(JSON, nullable=True)
    includeIndependentAssets = Column(Boolean, nullable=False, default=True, server_default=text('1'))
    accountGroupOrder = Column(JSON, nullable=True)
    showNotes = Column(Boolean, nullable=False, default=True, server_default=text('1'))
    idleMinutes = Column(Integer, nullable=False, default=30, server_default=text('30'))
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    updatedAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint('username', name='User_username_key'),)

class AgentCall(Base):
    __tablename__ = 'AgentCall'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    grantId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=False)
    tool = Column(VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False)
    status = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False)
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    __table_args__ = (Index('AgentCall_userId_createdAt_idx', 'userId', 'createdAt'),)

class AgentPolicy(Base):
    __tablename__ = 'AgentPolicy'
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), primary_key=True, nullable=False)
    mode = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False, default='draft', server_default=text("'draft'"))

class AgentClient(Base):
    __tablename__ = 'AgentClient'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=False)
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))

class AgentAuthorization(Base):
    __tablename__ = 'AgentAuthorization'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=True)
    clientId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=False)
    parameters = Column(JSON, nullable=False)
    codeDigest = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=True)
    expiresAt = Column(DATETIME(fsp=3), nullable=False)
    status = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False, default='pending', server_default=text("'pending'"))
    __table_args__ = (UniqueConstraint('codeDigest', name='AgentAuthorization_codeDigest_key'),)

class AgentGrant(Base):
    __tablename__ = 'AgentGrant'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    clientId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=True)
    name = Column(VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False)
    scopes = Column(JSON, nullable=False)
    resource = Column(VARCHAR(500, collation="utf8mb4_unicode_ci"), nullable=False)
    accessDigest = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=False)
    refreshDigest = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=True)
    expiresAt = Column(DATETIME(fsp=3), nullable=True)
    refreshExpiresAt = Column(DATETIME(fsp=3), nullable=True)
    revokedAt = Column(DATETIME(fsp=3), nullable=True)
    sessionId = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=False)
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    __table_args__ = (UniqueConstraint('accessDigest', name='AgentGrant_accessDigest_key'), UniqueConstraint('refreshDigest', name='AgentGrant_refreshDigest_key'), Index('AgentGrant_userId_createdAt_idx', 'userId', 'createdAt'),)

class AgentOperation(Base):
    __tablename__ = 'AgentOperation'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    grantId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=False)
    key = Column(VARCHAR(128, collation="utf8mb4_unicode_ci"), nullable=False)
    hash = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=False)
    tool = Column(VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False)
    parameters = Column(JSON, nullable=False)
    snapshot = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=False)
    status = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False, default='pending', server_default=text("'pending'"))
    expiresAt = Column(DATETIME(fsp=3), nullable=False)
    result = Column(JSON, nullable=True)
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    completedAt = Column(DATETIME(fsp=3), nullable=True)
    __table_args__ = (UniqueConstraint('userId', 'key', name='AgentOperation_userId_key_key'), Index('AgentOperation_userId_createdAt_idx', 'userId', 'createdAt'),)

class Session(Base):
    __tablename__ = 'Session'
    id = Column(CHAR(64, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False)
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    expiresAt = Column(DATETIME(fsp=3), nullable=False)
    lastActivity = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    revealUntil = Column(DATETIME(fsp=3), nullable=True)
    backupDigest = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=True)
    backupExpiresAt = Column(DATETIME(fsp=3), nullable=True)
    __table_args__ = (Index('Session_userId_idx', 'userId'),)

class Position(Base):
    __tablename__ = 'Position'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    importedFromId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=True)
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    kind = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False)
    side = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False)
    name = Column(VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False)
    category = Column(VARCHAR(40, collation="utf8mb4_unicode_ci"), nullable=False)
    groupName = Column(VARCHAR(60, collation="utf8mb4_unicode_ci"), nullable=False, default='', server_default=text("''"))
    currency = Column(CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False)
    notes = Column(TEXT(collation="utf8mb4_unicode_ci"), nullable=False)
    archived = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    hidden = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    included = Column(Boolean, nullable=False, default=True, server_default=text('1'))
    lastRepaymentMonth = Column(CHAR(7, collation="utf8mb4_unicode_ci"), nullable=True)
    lastBookedDate = Column(CHAR(10, collation="utf8mb4_unicode_ci"), nullable=True)
    metalType = Column(VARCHAR(12, collation="utf8mb4_unicode_ci"), nullable=True)
    metalGrams = Column(DECIMAL(24,8), nullable=True)
    metalPurity = Column(DECIMAL(12,8), nullable=False, default=1, server_default=text('1'))
    metalCostPerGram = Column(DECIMAL(24,12), nullable=True)
    autoValuation = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    updatedAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, onupdate=utcnow)
    iconId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('Icon.id', ondelete='SET NULL', onupdate="CASCADE"), nullable=True)
    __table_args__ = (Index('Position_userId_kind_idx', 'userId', 'kind'), UniqueConstraint('userId', 'importedFromId', name='Position_userId_importedFromId_key'),)

class Revision(Base):
    __tablename__ = 'Revision'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    sequence = Column(Integer, nullable=False, server_default=FetchedValue())
    positionId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('Position.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    amount = Column(DECIMAL(24,8), nullable=False)
    effectiveDate = Column(DATETIME(fsp=3), nullable=False)
    notes = Column(TEXT(collation="utf8mb4_unicode_ci"), nullable=False)
    reason = Column(VARCHAR(20, collation="utf8mb4_unicode_ci"), nullable=False)
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    updatedAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint('sequence', name='Revision_sequence_key'), Index('Revision_positionId_effectiveDate_sequence_idx', 'positionId', 'effectiveDate', 'sequence'), Index('Revision_positionId_reason_effectiveDate_sequence_idx', 'positionId', 'reason', 'effectiveDate', 'sequence'),)

class PositionLink(Base):
    __tablename__ = 'PositionLink'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    sourceId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('Position.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    targetId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('Position.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint('sourceId', 'targetId', name='PositionLink_sourceId_targetId_key'),)

class ExchangeRate(Base):
    __tablename__ = 'ExchangeRate'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    currency = Column(CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False)
    baseCurrency = Column(CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False)
    date = Column(Date, nullable=False)
    rate = Column(DECIMAL(24,12), nullable=False)
    source = Column(VARCHAR(30, collation="utf8mb4_unicode_ci"), nullable=False)
    __table_args__ = (UniqueConstraint('userId', 'currency', 'baseCurrency', 'date', name='ExchangeRate_userId_currency_baseCurrency_date_key'),)

class Icon(Base):
    __tablename__ = 'Icon'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    ownerId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='SET NULL', onupdate="CASCADE"), nullable=True)
    name = Column(VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False)
    shared = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    hash = Column(CHAR(64, collation="utf8mb4_unicode_ci"), nullable=False)
    data = Column(MEDIUMBLOB, nullable=False)
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    __table_args__ = (UniqueConstraint('ownerId', 'hash', 'shared', name='Icon_ownerId_hash_shared_key'), Index('Icon_shared_name_idx', 'shared', 'name'),)

class Transfer(Base):
    __tablename__ = 'Transfer'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    importedFromId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=True)
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    sourceId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('Position.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    targetId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('Position.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    sourceRevisionId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=False)
    targetRevisionId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=False)
    sourceCurrency = Column(CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False)
    targetCurrency = Column(CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False)
    amount = Column(DECIMAL(24,8), nullable=False)
    received = Column(DECIMAL(24,8), nullable=False)
    fee = Column(DECIMAL(24,8), nullable=False)
    effectiveDate = Column(DATETIME(fsp=3), nullable=False)
    notes = Column(TEXT(collation="utf8mb4_unicode_ci"), nullable=False)
    operation = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False, default='transfer', server_default=text("'transfer'"))
    createdAt = Column(DATETIME(fsp=3), nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP(3)"))
    __table_args__ = (UniqueConstraint('sourceRevisionId', name='Transfer_sourceRevisionId_key'), UniqueConstraint('targetRevisionId', name='Transfer_targetRevisionId_key'), UniqueConstraint('userId', 'importedFromId', name='Transfer_userId_importedFromId_key'), Index('Transfer_userId_effectiveDate_id_idx', 'userId', 'effectiveDate', 'id'),)

class Schedule(Base):
    __tablename__ = 'Schedule'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    importedFromId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=True)
    name = Column(VARCHAR(100, collation="utf8mb4_unicode_ci"), nullable=False)
    operation = Column(VARCHAR(16, collation="utf8mb4_unicode_ci"), nullable=False)
    sourceId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=False)
    targetId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), nullable=True)
    amount = Column(DECIMAL(24,8), nullable=False)
    received = Column(DECIMAL(24,8), nullable=False)
    nextAt = Column(DATETIME(fsp=3), nullable=False)
    intervalDays = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default=text('1'))
    completed = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    notes = Column(TEXT(collation="utf8mb4_unicode_ci"), nullable=False)
    __table_args__ = (Index('Schedule_userId_enabled_nextAt_idx', 'userId', 'enabled', 'nextAt'), UniqueConstraint('userId', 'importedFromId', name='Schedule_userId_importedFromId_key'),)

class MetalPrice(Base):
    __tablename__ = 'MetalPrice'
    id = Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, nullable=False, default=lambda: str(uuid4()))
    userId = Column(CHAR(36, collation="utf8mb4_unicode_ci"), ForeignKey('User.id', ondelete='CASCADE', onupdate="CASCADE"), nullable=False)
    metalType = Column(VARCHAR(12, collation="utf8mb4_unicode_ci"), nullable=False)
    currency = Column(CHAR(3, collation="utf8mb4_unicode_ci"), nullable=False)
    price = Column(DECIMAL(24,12), nullable=False)
    date = Column(Date, nullable=False)
    source = Column(VARCHAR(20, collation="utf8mb4_unicode_ci"), nullable=False)
    quotedAt = Column(DATETIME(fsp=3), nullable=False)
    __table_args__ = (UniqueConstraint('userId', 'metalType', 'currency', 'date', name='MetalPrice_userId_metalType_currency_date_key'),)
