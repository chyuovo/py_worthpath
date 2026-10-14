# 迁移清单

源提交：90b35bcb7197715ba193caf81f6047716089b188。源仓库既存 compose.yaml 修改保持不变。

## 前端

frontend/ 保留源 React 页面、组件、样式、国际化和静态文件；仅 Vite 环境变量读取位置改为前端自身目录。前后端无源码或依赖包引用。

| 文件 | 状态 |
| --- | --- |
| frontend/index.html | 原样保留（Vite 配置除外） |
| frontend/package.json | 原样保留（Vite 配置除外） |
| frontend/tsconfig.json | 原样保留（Vite 配置除外） |
| frontend/vite.config.ts | 原样保留（Vite 配置除外） |
| frontend/scripts/generate-locales.cjs | 原样保留（Vite 配置除外） |
| frontend/src/AccountPicker.tsx | 原样保留（Vite 配置除外） |
| frontend/src/AdminPanel.tsx | 原样保留（Vite 配置除外） |
| frontend/src/agent-display.ts | 原样保留（Vite 配置除外） |
| frontend/src/AgentConnections.tsx | 原样保留（Vite 配置除外） |
| frontend/src/AgentDrafts.tsx | 原样保留（Vite 配置除外） |
| frontend/src/AgentReview.tsx | 原样保留（Vite 配置除外） |
| frontend/src/api.ts | 原样保留（Vite 配置除外） |
| frontend/src/App.tsx | 原样保留（Vite 配置除外） |
| frontend/src/Calendar.tsx | 原样保留（Vite 配置除外） |
| frontend/src/DebtPaymentForm.tsx | 原样保留（Vite 配置除外） |
| frontend/src/FullScreenLoading.tsx | 原样保留（Vite 配置除外） |
| frontend/src/group-order.ts | 原样保留（Vite 配置除外） |
| frontend/src/GroupOrderContext.ts | 原样保留（Vite 配置除外） |
| frontend/src/GroupOrderList.tsx | 原样保留（Vite 配置除外） |
| frontend/src/i18n.tsx | 原样保留（Vite 配置除外） |
| frontend/src/IconLibrary.tsx | 原样保留（Vite 配置除外） |
| frontend/src/IconPicker.tsx | 原样保留（Vite 配置除外） |
| frontend/src/login-preferences.ts | 原样保留（Vite 配置除外） |
| frontend/src/main.tsx | 原样保留（Vite 配置除外） |
| frontend/src/MetalPanel.tsx | 原样保留（Vite 配置除外） |
| frontend/src/navigation.ts | 原样保留（Vite 配置除外） |
| frontend/src/NetWorthChart.tsx | 原样保留（Vite 配置除外） |
| frontend/src/overview-cards.ts | 原样保留（Vite 配置除外） |
| frontend/src/page-preferences.ts | 原样保留（Vite 配置除外） |
| frontend/src/PositionDeletion.tsx | 原样保留（Vite 配置除外） |
| frontend/src/PrimaryNav.tsx | 原样保留（Vite 配置除外） |
| frontend/src/PullToRefresh.tsx | 原样保留（Vite 配置除外） |
| frontend/src/QuickJournal.tsx | 原样保留（Vite 配置除外） |
| frontend/src/QuickTransfer.tsx | 原样保留（Vite 配置除外） |
| frontend/src/repayment.ts | 原样保留（Vite 配置除外） |
| frontend/src/request-loading.ts | 原样保留（Vite 配置除外） |
| frontend/src/SchedulePanel.tsx | 原样保留（Vite 配置除外） |
| frontend/src/style.css | 原样保留（Vite 配置除外） |
| frontend/src/Toast.tsx | 原样保留（Vite 配置除外） |
| frontend/src/TransferForm.tsx | 原样保留（Vite 配置除外） |
| frontend/test/i18n.test.ts | 原样保留（Vite 配置除外） |
| frontend/test/login-preferences.test.ts | 原样保留（Vite 配置除外） |
| frontend/test/net-worth-chart.test.ts | 原样保留（Vite 配置除外） |
| frontend/test/quick-entry.test.ts | 原样保留（Vite 配置除外） |
| frontend/src/locales/en.json | 原样保留（Vite 配置除外） |
| frontend/src/locales/zh-Hant.json | 原样保留（Vite 配置除外） |

## HTTP 契约

完整路径、方法、请求字段、错误响应、Cookie 认证及分页契约见 backend/app/openapi_contract.py；服务运行后可访问 /api/docs。

| 方法 | 路径 | 原模块 | 状态 |
| --- | --- | --- | --- |
| GET | /api/admin/users | admin.ts | 已实现，按回归结果核验 |
| POST | /api/admin/users | admin.ts | 已实现，按回归结果核验 |
| PATCH | /api/admin/users/:id | admin.ts | 已实现，按回归结果核验 |
| DELETE | /api/admin/users/:id | admin.ts | 已实现，按回归结果核验 |
| GET | /api/health | auth.ts | 已实现，按回归结果核验 |
| POST | /api/auth/register | auth.ts | 已实现，按回归结果核验 |
| POST | /api/auth/login | auth.ts | 已实现，按回归结果核验 |
| GET | /api/auth/me | auth.ts | 已实现，按回归结果核验 |
| PATCH | /api/auth/credentials | auth.ts | 已实现，按回归结果核验 |
| POST | /api/auth/activity | auth.ts | 已实现，按回归结果核验 |
| POST | /api/auth/reveal | auth.ts | 已实现，按回归结果核验 |
| POST | /api/auth/lock | auth.ts | 已实现，按回归结果核验 |
| POST | /api/auth/logout | auth.ts | 已实现，按回归结果核验 |
| GET | /api/backup | backup.ts | 已实现，按回归结果核验 |
| POST | /api/backup/upload | backup.ts | 已实现，按回归结果核验 |
| POST | /api/backup/import-file | backup.ts | 已实现，按回归结果核验 |
| GET | /api/backup/clear-status | backup.ts | 已实现，按回归结果核验 |
| POST | /api/backup/clear | backup.ts | 已实现，按回归结果核验 |
| GET | /api/calendar | calendar.ts | 已实现，按回归结果核验 |
| GET | /api/calendar/day | calendar.ts | 已实现，按回归结果核验 |
| GET | /api/icons | icons.ts | 已实现，按回归结果核验 |
| GET | /api/icons/:id/image | icons.ts | 已实现，按回归结果核验 |
| POST | /api/icons/upload | icons.ts | 已实现，按回归结果核验 |
| GET | /api/metals | metals.ts | 已实现，按回归结果核验 |
| POST | /api/metals/holdings | metals.ts | 已实现，按回归结果核验 |
| POST | /api/metals/refresh | metals.ts | 已实现，按回归结果核验 |
| PUT | /api/metals/:id | metals.ts | 已实现，按回归结果核验 |
| POST | /api/metals/:id/value | metals.ts | 已实现，按回归结果核验 |
| GET | /api/positions | portfolio.ts | 已实现，按回归结果核验 |
| GET | /api/positions/:id | portfolio.ts | 已实现，按回归结果核验 |
| GET | /api/history | portfolio.ts | 已实现，按回归结果核验 |
| GET | /api/positions/:id/history | portfolio.ts | 已实现，按回归结果核验 |
| GET | /api/trend | portfolio.ts | 已实现，按回归结果核验 |
| POST | /api/positions | portfolio.ts | 已实现，按回归结果核验 |
| PATCH | /api/positions/:id | portfolio.ts | 已实现，按回归结果核验 |
| PATCH | /api/positions/:id/inclusion | portfolio.ts | 已实现，按回归结果核验 |
| PATCH | /api/positions/:id/repayment-mark | portfolio.ts | 已实现，按回归结果核验 |
| GET | /api/positions/:id/deletion | portfolio.ts | 已实现，按回归结果核验 |
| DELETE | /api/positions/:id | portfolio.ts | 已实现，按回归结果核验 |
| POST | /api/positions/:id/revisions | portfolio.ts | 已实现，按回归结果核验 |
| PUT | /api/positions/:id/revisions/:revisionId | portfolio.ts | 已实现，按回归结果核验 |
| DELETE | /api/positions/:id/revisions/:revisionId | portfolio.ts | 已实现，按回归结果核验 |
| PUT | /api/positions/:id/links | portfolio.ts | 已实现，按回归结果核验 |
| GET | /api/overview | portfolio.ts | 已实现，按回归结果核验 |
| GET | /api/settings | rates.ts | 已实现，按回归结果核验 |
| PATCH | /api/settings | rates.ts | 已实现，按回归结果核验 |
| POST | /api/rates/refresh | rates.ts | 已实现，按回归结果核验 |
| GET | /api/schedules | schedules.ts | 已实现，按回归结果核验 |
| POST | /api/schedules | schedules.ts | 已实现，按回归结果核验 |
| PUT | /api/schedules/:id | schedules.ts | 已实现，按回归结果核验 |
| PATCH | /api/schedules/:id | schedules.ts | 已实现，按回归结果核验 |
| DELETE | /api/schedules/:id | schedules.ts | 已实现，按回归结果核验 |
| POST | /api/schedules/run | schedules.ts | 已实现，按回归结果核验 |
| GET | /api/transfers | transfers.ts | 已实现，按回归结果核验 |
| GET | /api/transfers/revision/:revisionId | transfers.ts | 已实现，按回归结果核验 |
| PUT | /api/transfers/:id | transfers.ts | 已实现，按回归结果核验 |
| DELETE | /api/transfers/:id | transfers.ts | 已实现，按回归结果核验 |
| POST | /api/transfers | transfers.ts | 已实现，按回归结果核验 |
| GET | /api/agent | management.ts | 已实现，按回归结果核验 |
| POST | /api/agent/tokens | management.ts | 已实现，按回归结果核验 |
| PATCH | /api/agent/connections/:id | management.ts | 已实现，按回归结果核验 |
| DELETE | /api/agent/connections/:id | management.ts | 已实现，按回归结果核验 |
| GET | /api/agent/authorizations/:id | management.ts | 已实现，按回归结果核验 |
| POST | /api/agent/authorizations/:id | management.ts | 已实现，按回归结果核验 |
| GET | /api/agent/drafts | management.ts | 已实现，按回归结果核验 |
| POST | /api/agent/operations/confirm-batch | management.ts | 已实现，按回归结果核验 |
| GET | /api/agent/operations/:id | management.ts | 已实现，按回归结果核验 |
| POST | /api/agent/operations/:id | management.ts | 已实现，按回归结果核验 |

## 返回值与通用规则

- 登录使用 wp_session HttpOnly Cookie；金额和重量为十进制字符串，时间戳为 UTC ISO，业务日期为 UTC+8。公开注册返回 403。普通 POST 成功沿用 201。
- 错误使用 { message }，参数错误 400、未登录 401、权限 403、对象不存在 404、并发或幂等冲突 409；不暴露 FastAPI 默认 422。
- positions 返回当前可见项目数组；detail 返回项目元数据、余额和贵金属成本/利润；全局及项目 history 返回 { items, nextCursor, revealed }，含真实前序余额、after、delta。
- overview 返回本位币、资产、负债、净资产、完整性、缺失汇率/估值及明细；trend 返回 from/to/grain/baseCurrency/revealed/items，按期末余额及每日归因采样。
- transfers 返回分页配对记录、双方项目名称及业务时间；create 返回 id；更新和撤销返回 ok。多表变更共用事务，历史调整后回放后续增量。
- settings 返回用户偏好、会话到期、隐藏解锁状态和最多 100 条可选汇率；日历返回月汇总或日明细；计划返回业务时间、启用及完成状态，run 返回 executed/errors/hasMore。
- 图标列表为 { items, total, page }，每页 60；图片为 PNG。备份为 ZIP v9；上传先返回预览及临时 token，恢复须明确 confirmed=true；清空须当前备份凭据与指纹匹配。
- MCP 返回文本 content 与 structuredContent.data；草稿返回 pending 和 confirmationUrl，网页批准后 operation_get 查询最终状态。文件票据绑定用户及连接。

## 数据库

16 个模型映射保留字段名与 MySQL 精度。不可变的完整字段、索引、外键、默认值、字符集和排序规则保存在 backend/alembic/baseline_schema.py；ORM 位于 backend/app/models.py。

模型：User, AgentCall, AgentPolicy, AgentClient, AgentAuthorization, AgentGrant, AgentOperation, Session, Position, Revision, PositionLink, ExchangeRate, Icon, Transfer, Schedule, MetalPrice。

已备份并接管现有测试库到 0001_existing_schema。只新增 alembic_version，不重建业务表。后续只使用 Alembic；原 Prisma 历史不再执行。

源项目历史迁移目录：

- 005_account_icons
- 006_navigation_transfers
- 007_notes_display
- 202610010001_initial
- 202610010002_import_origin
- 202610010003_revision_sequence
- 202610010004_privacy_time_settings
- 20261002000000_query_indexes
- 20261002000100_remove_global_revision_index
- 20261002000200_debt_movements
- 20261002000300_chinese_comments
- 20261002000400_groups_schedules
- 20261002000500_schedule_comments
- 20261003000100_account_group_order
- 20261003000200_session_display_settings
- 20261003000300_inclusion_metals
- 20261003000400_metal_source_comment
- 20261003090000_agent_access
- 20261003100000_agent_audit
- 20261003110000_agent_comments
- 20261003120000_metal_cost
- 20261003130000_migration_comments
- 20261004090000_agent_permanent_tokens
- 20261004103000_agent_connection_permissions
- 20261004110000_oauth_duration_comment
- 20261004154000_quick_repayment_month
- 20261004161000_quick_booked_date
- 20261005130000_admin_accounts
- 20261005150000_remove_icon_source

## 集成与业务模块

- OAuth：动态注册、PKCE S256、一次性授权码、刷新轮换、授权期限、撤销、只读角色及独立隐藏权限。
- MCP：32 个业务工具及 7 个协议工具，完整契约位于 backend/app/mcp_contracts.py。
- 网页计划按需执行，每批最多 20 项；不发起真实付款。
- Frankfurter 日汇率与 Gold API 贵金属报价；只请求固定公开参数，失败保留已有记录。
- ZIP v9 全量备份、追加恢复、来源去重、关系重建、私有图标恢复与备份后清空。

验收结果和边界见 README.md 与 VALIDATION.md。
