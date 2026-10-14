# MCP 运行契约：从源项目实际 Zod 定义提取，保留工具名、输入及描述。
CONTRACTS = {
    "tools": [
        {
            "name": "positions_list",
            "description": "查询账户、独立资产、借入借出债务。原币余额字符串；负债账户正数为欠款、负数为溢缴。支持名称搜索，重名不自动选择。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "limit": {
                        "default": 50,
                        "description": "单页上限 100",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "default": 0,
                        "description": "列表偏移；数据变化后从第一页重读",
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000000,
                    },
                    "kind": {"type": "string", "enum": ["account", "asset", "debt"]},
                    "q": {"type": "string", "maxLength": 100},
                    "archived": {"type": "boolean"},
                    "side": {"type": "string", "enum": ["asset", "liability"]},
                    "currency": {
                        "type": "string",
                        "enum": [
                            "CNY",
                            "USD",
                            "HKD",
                            "EUR",
                            "GBP",
                            "JPY",
                            "AUD",
                            "CAD",
                            "CHF",
                            "SGD",
                        ],
                    },
                    "groupName": {"type": "string", "maxLength": 60},
                    "order": {
                        "default": "id",
                        "type": "string",
                        "enum": ["name", "id"],
                    },
                },
                "required": ["limit", "offset", "order"],
                "additionalProperties": False,
            },
        },
        {
            "name": "position_get",
            "description": "查询项目详情、配置和当前原币余额。隐藏项目需网页解锁。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    }
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "position_create",
            "description": "新增账户、独立资产或债务及初始绝对余额。金额为十进制字符串，业务 date 为 YYYY-MM-DD 或 "
            "YYYY-MM-DDTHH:mm（UTC+8）。不新增日常消费功能。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "included": {"type": "boolean"},
                    "groupName": {"type": "string", "maxLength": 60},
                    "iconId": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "uuid",
                                "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                            },
                            {"type": "null"},
                        ]
                    },
                    "name": {"type": "string", "minLength": 1, "maxLength": 100},
                    "category": {"type": "string", "minLength": 1, "maxLength": 40},
                    "notes": {"default": "", "type": "string", "maxLength": 2000},
                    "archived": {"default": False, "type": "boolean"},
                    "hidden": {"default": False, "type": "boolean"},
                    "kind": {"type": "string", "enum": ["account", "asset", "debt"]},
                    "side": {"type": "string", "enum": ["asset", "liability"]},
                    "currency": {
                        "type": "string",
                        "enum": [
                            "CNY",
                            "USD",
                            "HKD",
                            "EUR",
                            "GBP",
                            "JPY",
                            "AUD",
                            "CAD",
                            "CHF",
                            "SGD",
                        ],
                    },
                    "amount": {
                        "type": "string",
                        "pattern": "^-?(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                    },
                    "date": {"type": "string"},
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": [
                    "name",
                    "category",
                    "notes",
                    "archived",
                    "hidden",
                    "kind",
                    "side",
                    "currency",
                    "amount",
                    "date",
                    "idempotencyKey",
                    "expectedState",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "position_update",
            "description": "修改名称、分类、分组、图标、备注、归档、隐藏、统计开关；币种和资产负债属性固定。须提供完整元数据。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "data": {
                        "type": "object",
                        "properties": {
                            "included": {"type": "boolean"},
                            "groupName": {"type": "string", "maxLength": 60},
                            "iconId": {
                                "anyOf": [
                                    {
                                        "type": "string",
                                        "format": "uuid",
                                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                                    },
                                    {"type": "null"},
                                ]
                            },
                            "name": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 100,
                            },
                            "category": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 40,
                            },
                            "notes": {
                                "default": "",
                                "type": "string",
                                "maxLength": 2000,
                            },
                            "archived": {"default": False, "type": "boolean"},
                            "hidden": {"default": False, "type": "boolean"},
                        },
                        "required": ["name", "category", "notes", "archived", "hidden"],
                        "additionalProperties": False,
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "data", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "balance_record",
            "description": "新增余额/估值/负债调整/单边还款历史：amount 是变更后的绝对余额，不是增量。资产估值使用 valuation；配对转账和还款使用 "
            "movement_create。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "data": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": "string",
                                "pattern": "^-?(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "date": {"type": "string"},
                            "notes": {
                                "default": "",
                                "type": "string",
                                "maxLength": 2000,
                            },
                            "reason": {
                                "default": "balance",
                                "type": "string",
                                "enum": [
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
                                ],
                            },
                        },
                        "required": ["amount", "date", "notes", "reason"],
                        "additionalProperties": False,
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "data", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "history_list",
            "description": "分页查询全局或单项目历史，业务时间降序；返回真实前序余额。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "limit": {
                        "default": 50,
                        "description": "单页上限 100",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "cursor": {
                        "description": "上一页 nextCursor",
                        "type": "string",
                        "maxLength": 512,
                    },
                    "from": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "to": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "positionId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                },
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
        {
            "name": "history_update",
            "description": "更正单条非配对历史，自动重放后续金额；配对记录使用 movement_update。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "revisionId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "data": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": "string",
                                "pattern": "^-?(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "date": {"type": "string"},
                            "notes": {
                                "default": "",
                                "type": "string",
                                "maxLength": 2000,
                            },
                            "reason": {
                                "default": "balance",
                                "type": "string",
                                "enum": [
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
                                ],
                            },
                        },
                        "required": ["amount", "date", "notes", "reason"],
                        "additionalProperties": False,
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": [
                    "id",
                    "revisionId",
                    "data",
                    "idempotencyKey",
                    "expectedState",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "history_delete",
            "description": "删除历史并重算；配对历史会撤销完整双边操作。",
            "scope": "write",
            "destructive": True,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "revisionId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "revisionId", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "debt_links_set",
            "description": "替换债务与自己账户/资产的关联，不参与金额求和。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "targetIds": {
                        "maxItems": 20,
                        "type": "array",
                        "items": {
                            "type": "string",
                            "format": "uuid",
                            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                            "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 "
                            "ID",
                        },
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "targetIds", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "overview_get",
            "description": "净资产、资产负债总额、结构及变化归因；遵循逐项目和独立资产纳入设置。明细分页。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "limit": {
                        "default": 50,
                        "description": "单页上限 100",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "default": 0,
                        "description": "列表偏移；数据变化后从第一页重读",
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000000,
                    },
                },
                "required": ["limit", "offset"],
                "additionalProperties": False,
            },
        },
        {
            "name": "trend_get",
            "description": "净资产趋势，缺失汇率不绘制完整总额。业务日 YYYY-MM-DD；支持日/周/月粒度。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "from": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "to": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "grain": {"type": "string", "enum": ["day", "week", "month"]},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "movements_list",
            "description": "查询转账、借入、借出、收款、还款配对记录，分页和业务日期筛选。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "limit": {
                        "default": 50,
                        "description": "单页上限 100",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "cursor": {
                        "description": "上一页 nextCursor",
                        "type": "string",
                        "maxLength": 512,
                    },
                    "from": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "to": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                },
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
        {
            "name": "movement_by_revision",
            "description": "根据历史 UUID 找到对应双边记录。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "revisionId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    }
                },
                "required": ["revisionId"],
                "additionalProperties": False,
            },
        },
        {
            "name": "movement_create",
            "description": "执行 transfer 转账、borrow 借入、lend 借出、collect 收款、repay 还款。amount 为本金，received "
            "为到账/债务本金，fee 可负表示优惠；原币十进制字符串，双边事务和余额检查。repay 的 sourceId 必须是资产账户，targetId "
            "可以是借入债务或信用卡等负债账户；负债账户超额还款保留为存款。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "operation": {
                        "default": "transfer",
                        "type": "string",
                        "enum": ["transfer", "borrow", "lend", "collect", "repay"],
                    },
                    "requestId": {"not": {}},
                    "sourceId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    },
                    "targetId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    },
                    "amount": {
                        "type": "string",
                        "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                    },
                    "received": {
                        "type": "string",
                        "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                    },
                    "fee": {
                        "default": "0",
                        "type": "string",
                        "pattern": "^-?(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                    },
                    "date": {"type": "string"},
                    "notes": {"default": "", "type": "string", "maxLength": 2000},
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": [
                    "operation",
                    "sourceId",
                    "targetId",
                    "amount",
                    "received",
                    "fee",
                    "date",
                    "notes",
                    "idempotencyKey",
                    "expectedState",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "movement_update",
            "description": "修改完整双边资金往来并重放后续历史，保持余额一致。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "data": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "default": "transfer",
                                "type": "string",
                                "enum": [
                                    "transfer",
                                    "borrow",
                                    "lend",
                                    "collect",
                                    "repay",
                                ],
                            },
                            "requestId": {"not": {}},
                            "sourceId": {
                                "type": "string",
                                "format": "uuid",
                                "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                            },
                            "targetId": {
                                "type": "string",
                                "format": "uuid",
                                "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                            },
                            "amount": {
                                "type": "string",
                                "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "received": {
                                "type": "string",
                                "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "fee": {
                                "default": "0",
                                "type": "string",
                                "pattern": "^-?(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "date": {"type": "string"},
                            "notes": {
                                "default": "",
                                "type": "string",
                                "maxLength": 2000,
                            },
                        },
                        "required": [
                            "operation",
                            "sourceId",
                            "targetId",
                            "amount",
                            "received",
                            "fee",
                            "date",
                            "notes",
                        ],
                        "additionalProperties": False,
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "data", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "movement_delete",
            "description": "撤销完整双边转账/借贷/还款并重算后续余额。",
            "scope": "write",
            "destructive": True,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "calendar_month",
            "description": "月日历现金流统计；YYYY-MM，时区 UTC+8。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "month": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"}
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "calendar_day",
            "description": "查询某业务日的收入支出变化明细，分页。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "limit": {
                        "default": 50,
                        "description": "单页上限 100",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "default": 0,
                        "description": "列表偏移；数据变化后从第一页重读",
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000000,
                    },
                    "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                },
                "required": ["limit", "offset"],
                "additionalProperties": False,
            },
        },
        {
            "name": "schedules_list",
            "description": "计划列表及启用、完成状态，按到期时间排序。执行记录也可在 history_list 查询。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "limit": {
                        "default": 50,
                        "description": "单页上限 100",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "default": 0,
                        "description": "列表偏移；数据变化后从第一页重读",
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000000,
                    },
                },
                "required": ["limit", "offset"],
                "additionalProperties": False,
            },
        },
        {
            "name": "schedule_create",
            "description": "新增现有支出或转账计划。nextAt 为 YYYY-MM-DDTHH:mm（UTC+8），intervalDays=0 表示一次。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 100},
                    "operation": {"type": "string", "enum": ["expense", "transfer"]},
                    "sourceId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    },
                    "targetId": {
                        "default": None,
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "uuid",
                                "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                            },
                            {"type": "null"},
                        ],
                    },
                    "amount": {
                        "type": "string",
                        "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                    },
                    "received": {
                        "default": "0",
                        "type": "string",
                        "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                    },
                    "nextAt": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}$",
                    },
                    "intervalDays": {"type": "integer", "minimum": 0, "maximum": 3650},
                    "notes": {"default": "", "type": "string", "maxLength": 2000},
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": [
                    "name",
                    "operation",
                    "sourceId",
                    "targetId",
                    "amount",
                    "received",
                    "nextAt",
                    "intervalDays",
                    "notes",
                    "idempotencyKey",
                    "expectedState",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "schedule_update",
            "description": "修改未完成计划的完整配置。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "data": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 100,
                            },
                            "operation": {
                                "type": "string",
                                "enum": ["expense", "transfer"],
                            },
                            "sourceId": {
                                "type": "string",
                                "format": "uuid",
                                "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                            },
                            "targetId": {
                                "default": None,
                                "anyOf": [
                                    {
                                        "type": "string",
                                        "format": "uuid",
                                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                                    },
                                    {"type": "null"},
                                ],
                            },
                            "amount": {
                                "type": "string",
                                "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "received": {
                                "default": "0",
                                "type": "string",
                                "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "nextAt": {
                                "type": "string",
                                "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}$",
                            },
                            "intervalDays": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 3650,
                            },
                            "notes": {
                                "default": "",
                                "type": "string",
                                "maxLength": 2000,
                            },
                        },
                        "required": [
                            "name",
                            "operation",
                            "sourceId",
                            "targetId",
                            "amount",
                            "received",
                            "nextAt",
                            "intervalDays",
                            "notes",
                        ],
                        "additionalProperties": False,
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "data", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "schedule_toggle",
            "description": "启用或停用计划；已完成一次性计划不可重启。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "enabled": {"type": "boolean"},
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "enabled", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "schedule_delete",
            "description": "删除计划；保留已完成的金额历史。",
            "scope": "write",
            "destructive": True,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "schedules_run",
            "description": "以事务执行最多 20 个已到期计划，任一失败回滚本批；可按 hasMore 分批继续。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "settings_get",
            "description": "个人资料、本位币、显示菜单、备注、隐私、总览卡片、账户分组顺序及汇率状态；不返回密码或令牌。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "settings_update",
            "description": "修改个人设置、本位币、分组排序、登录时长及纳入统计配置。安全设置仅在网站修改。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "baseCurrency": {
                        "type": "string",
                        "enum": [
                            "CNY",
                            "USD",
                            "HKD",
                            "EUR",
                            "GBP",
                            "JPY",
                            "AUD",
                            "CAD",
                            "CHF",
                            "SGD",
                        ],
                    },
                    "hiddenMenus": {
                        "maxItems": 7,
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "overview",
                                "account",
                                "asset",
                                "debt",
                                "history",
                                "calendar",
                                "schedules",
                            ],
                        },
                    },
                    "accountGroupOrder": {
                        "maxItems": 1000,
                        "type": "array",
                        "items": {"type": "string", "maxLength": 60},
                    },
                    "showNotes": {"type": "boolean"},
                    "idleMinutes": {"type": "integer", "minimum": 0, "maximum": 1440},
                    "sessionHours": {"not": {}},
                    "requireHiddenPassword": {"not": {}},
                    "overviewCards": {
                        "maxItems": 7,
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "assets",
                                "liabilities",
                                "net",
                                "trend",
                                "composition",
                                "recent",
                                "attribution",
                            ],
                        },
                    },
                    "includeIndependentAssets": {"type": "boolean"},
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "metal_holding_create",
            "description": "按克数创建金银资产，无需市场价格；买入每克成本可选，缺少报价时待估值。日期为 UTC+8 业务时间。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "metalType": {"type": "string", "enum": ["gold", "silver"]},
                    "metalGrams": {
                        "type": "string",
                        "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                    },
                    "metalCostPerGram": {
                        "description": "每克实物买入成本，原币十进制字符串；null "
                        "清除成本，省略保留",
                        "anyOf": [
                            {
                                "type": "string",
                                "pattern": "^(0|[1-9]\\d{0,11})(\\.\\d{1,12})?$",
                            },
                            {"type": "null"},
                        ],
                    },
                    "autoValuation": {"type": "boolean"},
                    "name": {"type": "string", "minLength": 1, "maxLength": 100},
                    "currency": {
                        "type": "string",
                        "enum": [
                            "CNY",
                            "USD",
                            "HKD",
                            "EUR",
                            "GBP",
                            "JPY",
                            "AUD",
                            "CAD",
                            "CHF",
                            "SGD",
                        ],
                    },
                    "notes": {"default": "", "type": "string", "maxLength": 2000},
                    "hidden": {"default": False, "type": "boolean"},
                    "included": {"default": True, "type": "boolean"},
                    "date": {"type": "string"},
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": [
                    "metalType",
                    "metalGrams",
                    "autoValuation",
                    "name",
                    "currency",
                    "notes",
                    "hidden",
                    "included",
                    "date",
                    "idempotencyKey",
                    "expectedState",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "metals_prices",
            "description": "最近 100 条金银每克报价和更新状态。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "metal_configure",
            "description": "设置金银重量和自动估值，复用现有估值规则。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "data": {
                        "type": "object",
                        "properties": {
                            "metalType": {"type": "string", "enum": ["gold", "silver"]},
                            "metalGrams": {
                                "type": "string",
                                "pattern": "^(0|[1-9]\\d{0,15})(\\.\\d{1,8})?$",
                            },
                            "metalCostPerGram": {
                                "description": "每克实物买入成本，原币十进制字符串；null "
                                "清除成本，省略保留",
                                "anyOf": [
                                    {
                                        "type": "string",
                                        "pattern": "^(0|[1-9]\\d{0,11})(\\.\\d{1,12})?$",
                                    },
                                    {"type": "null"},
                                ],
                            },
                            "autoValuation": {"type": "boolean"},
                        },
                        "required": ["metalType", "metalGrams", "autoValuation"],
                        "additionalProperties": False,
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "data", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "metal_value",
            "description": "按已有报价为指定贵金属资产生成估值历史。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                        "description": "稳定对象 UUID；名称重名时先搜索，再由用户选择 ID",
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": ["id", "idempotencyKey", "expectedState"],
                "additionalProperties": False,
            },
        },
        {
            "name": "icons_list",
            "description": "搜索私有或共享图标，固定单页 60 个；使用返回 ID 配置项目图标。",
            "scope": "read",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "q": {"default": "", "type": "string", "maxLength": 100},
                    "page": {
                        "default": 1,
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100000,
                    },
                },
                "required": ["q", "page"],
                "additionalProperties": False,
            },
        },
        {
            "name": "icon_publish",
            "description": "保存已上传私有图标，不允许发布共享图标。先 file_upload_request(kind=icon)。",
            "scope": "write",
            "destructive": False,
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "fileId": {
                        "type": "string",
                        "format": "uuid",
                        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    },
                    "name": {"type": "string", "minLength": 1, "maxLength": 100},
                    "shared": {"default": False, "type": "boolean", "const": False},
                    "idempotencyKey": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 128,
                        "pattern": "^[A-Za-z0-9_.:-]+$",
                        "description": "同用户唯一幂等键；重试使用相同键和全部参数，改动参数必须换键",
                    },
                    "expectedState": {
                        "type": "string",
                        "pattern": "^[a-f0-9]{64}$",
                        "description": "先 state_get 获取 "
                        "state，避免覆盖并发修改；状态变化后重新读取并使用新幂等键",
                    },
                },
                "required": [
                    "fileId",
                    "name",
                    "shared",
                    "idempotencyKey",
                    "expectedState",
                ],
                "additionalProperties": False,
            },
        },
    ],
    "protocolTools": [
        {
            "name": "state_get",
            "description": "读取当前账目并发版本，作为下一次写入的 expectedState。",
            "scope": "read",
        },
        {
            "name": "operation_get",
            "description": "查询本连接发起的草稿、确认状态和最终结果。",
            "scope": "read",
        },
        {
            "name": "file_upload_request",
            "description": "请求受保护的私有图标上传入口，不直接修改账目。",
            "scope": "write",
        },
        {
            "name": "file_status",
            "description": "查询本连接上传文件状态和导入预检。",
            "scope": "read",
        },
        {
            "name": "icon_image",
            "description": "请求受保护的图标图片读取入口。",
            "scope": "read",
        },
        {
            "name": "connection_info",
            "description": "查看本连接权限、期限和隐藏账户授权。",
            "scope": "read",
        },
        {
            "name": "connection_revoke",
            "description": "撤销本连接；只读权限下也可主动撤销自身。",
            "scope": "read",
        },
    ],
}
