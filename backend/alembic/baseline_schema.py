# 已核对的不可变 MySQL 基线结构；只包含 DDL，不包含数据或凭据。
SCHEMA = {'User': 'CREATE TABLE `User` (\n'
         "  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
         "  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录用户名，唯一',\n"
         "  `passwordHash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录密码的 "
         "bcrypt 哈希，不存储明文',\n"
         "  `baseCurrency` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'CNY' COMMENT "
         "'本位币代码',\n"
         "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC',\n"
         "  `updatedAt` datetime(3) NOT NULL COMMENT '记录更新时间，UTC',\n"
         "  `idleMinutes` int NOT NULL DEFAULT '30' COMMENT '无操作退出分钟数，0 表示关闭',\n"
         "  `hiddenMenus` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT "
         "'隐藏菜单标识列表',\n"
         "  `showNotes` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否显示备注',\n"
         "  `accountGroupOrder` json DEFAULT NULL COMMENT '账户分组显示顺序；空值表示沿用默认顺序',\n"
         "  `sessionHours` int NOT NULL DEFAULT '168' COMMENT '登录有效时长（小时），范围 1 至 720',\n"
         "  `requireHiddenPassword` tinyint(1) NOT NULL DEFAULT '1' COMMENT '查看隐藏项目是否需要再次验证密码',\n"
         "  `overviewCards` json DEFAULT NULL COMMENT '总览显示的卡片键列表，NULL 表示默认全部显示',\n"
         "  `includeIndependentAssets` tinyint(1) NOT NULL DEFAULT '1' COMMENT '独立资产是否参与资产总览和净资产轨迹',\n"
         "  `role` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user' COMMENT '系统权限：admin、user 或 "
         "readonly；管理员不能查看其他用户财务数据',\n"
         "  `banned` tinyint(1) NOT NULL DEFAULT '0' COMMENT '封禁后禁止登录和使用已有会话、MCP 授权',\n"
         "  `mustChangePassword` tinyint(1) NOT NULL DEFAULT '0' COMMENT '首次登录必须设置新的强密码',\n"
         '  PRIMARY KEY (`id`),\n'
         '  UNIQUE KEY `User_username_key` (`username`)\n'
         ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户及个人设置'",
 'AgentCall': 'CREATE TABLE `AgentCall` (\n'
              "  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '审计标识',\n"
              "  `userId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
              "  `grantId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '调用所属连接标识',\n"
              "  `tool` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '调用的工具名称',\n"
              "  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '结果状态：success 或 error',\n"
              "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '调用完成时间，UTC',\n"
              '  PRIMARY KEY (`id`),\n'
              '  KEY `AgentCall_userId_createdAt_idx` (`userId`,`createdAt`),\n'
              '  CONSTRAINT `AgentCall_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE CASCADE '
              'ON UPDATE CASCADE\n'
              ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MCP 调用审计，不保存参数、密码、令牌或财务内容'",
 'AgentPolicy': 'CREATE TABLE `AgentPolicy` (\n'
                "  `userId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
                "  `mode` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'draft' COMMENT '写入策略：readonly "
                "只读、draft 草稿、direct 普通直接写入',\n"
                '  PRIMARY KEY (`userId`),\n'
                '  CONSTRAINT `AgentPolicy_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE '
                'CASCADE ON UPDATE CASCADE\n'
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='已停用的历史 Agent "
                "策略数据，保留原数据但不参与权限判定'",
 'AgentClient': 'CREATE TABLE `AgentClient` (\n'
                "  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
                "  `metadata` json NOT NULL COMMENT '公开客户端注册元数据，不保存用户凭据',\n"
                "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',\n"
                '  PRIMARY KEY (`id`)\n'
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='OAuth 动态注册客户端元数据'",
 'AgentAuthorization': 'CREATE TABLE `AgentAuthorization` (\n'
                       "  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
                       "  `userId` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '所属用户标识，用于数据隔离',\n"
                       "  `clientId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'OAuth 客户端标识；个人令牌为空',\n"
                       "  `parameters` json NOT NULL COMMENT '具体操作参数；禁止保存密码及令牌',\n"
                       "  `codeDigest` char(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '一次性授权码 SHA-256 摘要',\n"
                       "  `expiresAt` datetime(3) NOT NULL COMMENT '到期时间，UTC',\n"
                       "  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT "
                       "'当前处理状态',\n"
                       '  PRIMARY KEY (`id`),\n'
                       '  UNIQUE KEY `AgentAuthorization_codeDigest_key` (`codeDigest`),\n'
                       '  KEY `AgentAuthorization_userId_fkey` (`userId`),\n'
                       '  CONSTRAINT `AgentAuthorization_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) '
                       'ON DELETE CASCADE ON UPDATE CASCADE\n'
                       ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='短期 OAuth "
                       "授权请求及一次性授权码摘要'",
 'AgentGrant': 'CREATE TABLE `AgentGrant` (\n'
               "  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
               "  `userId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
               "  `clientId` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'OAuth 客户端标识；个人令牌为空',\n"
               "  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户可见连接名称',\n"
               "  `scopes` json NOT NULL COMMENT '权限列表：read、draft 或 write；隐藏账户附加权限 hidden_read、hidden_write',\n"
               "  `resource` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '令牌适用的规范 MCP 资源地址',\n"
               "  `accessDigest` char(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '访问令牌 SHA-256 摘要；完整值仅颁发时返回',\n"
               "  `refreshDigest` char(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '刷新令牌 SHA-256 摘要，使用后轮换',\n"
               "  `expiresAt` datetime(3) DEFAULT NULL COMMENT '访问令牌到期时间，UTC；空表示可撤销的永久个人令牌',\n"
               "  `refreshExpiresAt` datetime(3) DEFAULT NULL COMMENT '刷新授权到期时间，UTC；空表示永久 OAuth 授权或个人令牌不适用',\n"
               "  `revokedAt` datetime(3) DEFAULT NULL COMMENT '撤销时间，UTC；空表示未撤销',\n"
               "  `sessionId` char(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '本连接的独立业务授权会话标识，不作为 MCP 凭证',\n"
               "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',\n"
               '  PRIMARY KEY (`id`),\n'
               '  UNIQUE KEY `AgentGrant_accessDigest_key` (`accessDigest`),\n'
               '  UNIQUE KEY `AgentGrant_refreshDigest_key` (`refreshDigest`),\n'
               '  KEY `AgentGrant_userId_createdAt_idx` (`userId`,`createdAt`),\n'
               '  CONSTRAINT `AgentGrant_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE '
               'CASCADE ON UPDATE CASCADE\n'
               ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户授权连接、令牌摘要及资源权限'",
 'AgentOperation': 'CREATE TABLE `AgentOperation` (\n'
                   "  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
                   "  `userId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
                   "  `grantId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '发起操作的授权连接标识',\n"
                   "  `key` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '同用户唯一的客户端幂等键',\n"
                   "  `hash` char(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '工具和参数的规范摘要；拒绝同键不同参数',\n"
                   "  `tool` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '业务工具名称',\n"
                   "  `parameters` json NOT NULL COMMENT '具体操作参数；禁止保存密码及令牌',\n"
                   "  `snapshot` char(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '确认前的账目版本摘要，防止覆盖并发修改',\n"
                   "  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '当前处理状态',\n"
                   "  `expiresAt` datetime(3) NOT NULL COMMENT '到期时间，UTC',\n"
                   "  `result` json DEFAULT NULL COMMENT '结构化操作结果或最近提交失败原因',\n"
                   "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',\n"
                   "  `completedAt` datetime(3) DEFAULT NULL COMMENT '完成或取消时间，UTC',\n"
                   '  PRIMARY KEY (`id`),\n'
                   '  UNIQUE KEY `AgentOperation_userId_key_key` (`userId`,`key`),\n'
                   '  KEY `AgentOperation_userId_createdAt_idx` (`userId`,`createdAt`),\n'
                   '  CONSTRAINT `AgentOperation_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON '
                   'DELETE CASCADE ON UPDATE CASCADE\n'
                   ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent 写入草稿、幂等记录及提交结果'",
 'Session': 'CREATE TABLE `Session` (\n'
            "  `id` char(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '随机会话令牌的 SHA-256 摘要',\n"
            "  `userId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
            "  `expiresAt` datetime(3) NOT NULL COMMENT '会话过期时间，UTC',\n"
            "  `lastActivity` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '最后有效交互时间，UTC',\n"
            "  `revealUntil` datetime(3) DEFAULT NULL COMMENT '隐藏项目授权截止时间，UTC；空表示未解锁',\n"
            "  `backupDigest` char(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '已下载备份内容的 "
            "SHA-256 摘要',\n"
            "  `backupExpiresAt` datetime(3) DEFAULT NULL COMMENT '备份清空确认凭据截止时间，UTC',\n"
            '  PRIMARY KEY (`id`),\n'
            '  KEY `Session_userId_idx` (`userId`),\n'
            '  CONSTRAINT `Session_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE CASCADE ON '
            'UPDATE CASCADE\n'
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录会话与隐藏项目查看授权'",
 'Position': 'CREATE TABLE `Position` (\n'
             "  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
             "  `userId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
             "  `kind` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '项目类型：account "
             "账户、asset 独立资产、debt 债务',\n"
             "  `side` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '统计方向：asset "
             "资产或借出应收、liability 负债或借入应付',\n"
             "  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '显示名称',\n"
             "  `category` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '项目分类代码',\n"
             "  `currency` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '原始币种代码',\n"
             "  `notes` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户备注，原文保留',\n"
             "  `archived` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否归档；归档项目仍计入总额',\n"
             "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC',\n"
             "  `updatedAt` datetime(3) NOT NULL COMMENT '记录更新时间，UTC',\n"
             '  `importedFromId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '
             "'备份导入来源项目标识，用于重复导入识别',\n"
             "  `hidden` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否隐藏；未解锁时不参与可见范围统计',\n"
             "  `iconId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '关联账户图标标识',\n"
             "  `groupName` varchar(60) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '自定义账户分组',\n"
             "  `included` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否参与资产负债总额及净资产轨迹',\n"
             "  `metalType` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '贵金属品种：gold 黄金或 silver 白银',\n"
             "  `metalGrams` decimal(24,8) DEFAULT NULL COMMENT '贵金属总重量，单位克',\n"
             "  `metalPurity` decimal(12,8) NOT NULL DEFAULT '1.00000000' COMMENT '贵金属纯度比例，0 至 1',\n"
             "  `autoValuation` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否随每日价格更新自动记录估值',\n"
             "  `metalCostPerGram` decimal(24,12) DEFAULT NULL COMMENT '买入时每克实物成本，原币；空值表示不计算盈亏',\n"
             "  `lastRepaymentMonth` char(7) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '最后手动标记已完成还款的业务月份，UTC+8 "
             "YYYY-MM；空表示未标记',\n"
             "  `lastBookedDate` char(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '最后手动标记已完成记账的业务日期，UTC+8 "
             "YYYY-MM-DD；空表示未标记',\n"
             '  PRIMARY KEY (`id`),\n'
             '  UNIQUE KEY `Position_userId_importedFromId_key` (`userId`,`importedFromId`),\n'
             '  KEY `Position_userId_kind_idx` (`userId`,`kind`),\n'
             '  KEY `Position_iconId_fkey` (`iconId`),\n'
             '  CONSTRAINT `Position_iconId_fkey` FOREIGN KEY (`iconId`) REFERENCES `Icon` (`id`) ON DELETE SET NULL '
             'ON UPDATE CASCADE,\n'
             '  CONSTRAINT `Position_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE CASCADE ON '
             'UPDATE CASCADE\n'
             ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='持有项目：账户、独立资产和借入借出债务'",
 'Revision': 'CREATE TABLE `Revision` (\n'
             "  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
             "  `positionId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属持有项目标识',\n"
             "  `amount` decimal(24,8) NOT NULL COMMENT '变更后的原币绝对余额，不是收支增量，禁止对全部历史求和',\n"
             "  `effectiveDate` datetime(3) NOT NULL COMMENT '北京时间业务时间对应的 UTC，精确到分钟',\n"
             "  `notes` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户备注，原文保留',\n"
             '  `reason` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '
             "'变更原因：初始、余额、估值、转账或借贷配对操作',\n"
             "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC',\n"
             "  `updatedAt` datetime(3) NOT NULL COMMENT '记录更新时间，UTC',\n"
             "  `sequence` int NOT NULL AUTO_INCREMENT COMMENT '数据库自增唯一顺序，同业务时间按此排序',\n"
             '  PRIMARY KEY (`id`),\n'
             '  UNIQUE KEY `Revision_sequence_key` (`sequence`),\n'
             '  KEY `Revision_positionId_effectiveDate_sequence_idx` (`positionId`,`effectiveDate`,`sequence`),\n'
             '  KEY `Revision_positionId_reason_effectiveDate_sequence_idx` '
             '(`positionId`,`reason`,`effectiveDate`,`sequence`),\n'
             '  CONSTRAINT `Revision_positionId_fkey` FOREIGN KEY (`positionId`) REFERENCES `Position` (`id`) ON '
             'DELETE CASCADE ON UPDATE CASCADE\n'
             ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='余额历史：金额为变更后的绝对余额'",
 'PositionLink': 'CREATE TABLE `PositionLink` (\n'
                 "  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
                 '  `sourceId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '
                 "'关联来源项目标识，通常为债务',\n"
                 '  `targetId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '
                 "'关联目标项目标识，通常为账户或资产',\n"
                 '  PRIMARY KEY (`id`),\n'
                 '  UNIQUE KEY `PositionLink_sourceId_targetId_key` (`sourceId`,`targetId`),\n'
                 '  KEY `PositionLink_targetId_fkey` (`targetId`),\n'
                 '  CONSTRAINT `PositionLink_sourceId_fkey` FOREIGN KEY (`sourceId`) REFERENCES `Position` (`id`) ON '
                 'DELETE CASCADE ON UPDATE CASCADE,\n'
                 '  CONSTRAINT `PositionLink_targetId_fkey` FOREIGN KEY (`targetId`) REFERENCES `Position` (`id`) ON '
                 'DELETE CASCADE ON UPDATE CASCADE\n'
                 ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='项目关联关系，不参与金额求和'",
 'ExchangeRate': 'CREATE TABLE `ExchangeRate` (\n'
                 "  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
                 '  `userId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '
                 "'所属用户标识，用于数据隔离',\n"
                 "  `currency` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '原始币种代码',\n"
                 "  `baseCurrency` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '本位币代码',\n"
                 "  `date` date NOT NULL COMMENT '汇率业务日期',\n"
                 "  `rate` decimal(24,12) NOT NULL COMMENT '每单位原币对应的本位币金额',\n"
                 '  `source` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '
                 "'汇率来源标识，保留已有历史来源',\n"
                 '  PRIMARY KEY (`id`),\n'
                 '  UNIQUE KEY `ExchangeRate_userId_currency_baseCurrency_date_key` '
                 '(`userId`,`currency`,`baseCurrency`,`date`),\n'
                 '  CONSTRAINT `ExchangeRate_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE '
                 'CASCADE ON UPDATE CASCADE\n'
                 ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户原币兑本位币的历史汇率'",
 'Icon': 'CREATE TABLE `Icon` (\n'
         "  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
         '  `ownerId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '
         "'上传用户标识；空可表示系统图标或原用户已删除',\n"
         "  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '显示名称',\n"
         "  `shared` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否公开共享给已登录用户',\n"
         "  `hash` char(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '规范化图标内容的 SHA-256 摘要',\n"
         "  `data` mediumblob NOT NULL COMMENT '规范化静态 PNG 图片二进制',\n"
         "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC',\n"
         '  PRIMARY KEY (`id`),\n'
         '  UNIQUE KEY `Icon_ownerId_hash_shared_key` (`ownerId`,`hash`,`shared`),\n'
         '  KEY `Icon_shared_name_idx` (`shared`,`name`),\n'
         '  CONSTRAINT `Icon_ownerId_fkey` FOREIGN KEY (`ownerId`) REFERENCES `User` (`id`) ON DELETE SET NULL ON '
         'UPDATE CASCADE\n'
         ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='可复用账户图标'",
 'Transfer': 'CREATE TABLE `Transfer` (\n'
             "  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
             '  `importedFromId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '
             "'备份导入来源项目标识，用于重复导入识别',\n"
             "  `userId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
             "  `sourceId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '来源资产账户标识',\n"
             "  `targetId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '目标账户或债务标识',\n"
             '  `sourceRevisionId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '
             "'来源账户配对余额历史标识',\n"
             '  `targetRevisionId` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '
             "'目标项目配对余额历史标识',\n"
             "  `sourceCurrency` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '来源账户币种',\n"
             "  `targetCurrency` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '目标项目币种',\n"
             "  `amount` decimal(24,8) NOT NULL COMMENT '本次来源账户本金金额，不是变更后余额',\n"
             "  `received` decimal(24,8) NOT NULL COMMENT '本次目标到账金额或债务本金金额',\n"
             "  `fee` decimal(24,8) NOT NULL COMMENT '来源币种手续费；负数表示优惠',\n"
             "  `effectiveDate` datetime(3) NOT NULL COMMENT '北京时间业务时间对应的 UTC，精确到分钟',\n"
             "  `notes` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户备注，原文保留',\n"
             "  `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC',\n"
             "  `operation` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'transfer' "
             "COMMENT '操作类型：transfer 转账、borrow 借入、lend 借出、collect 收款、repay 还款',\n"
             '  PRIMARY KEY (`id`),\n'
             '  UNIQUE KEY `Transfer_sourceRevisionId_key` (`sourceRevisionId`),\n'
             '  UNIQUE KEY `Transfer_targetRevisionId_key` (`targetRevisionId`),\n'
             '  UNIQUE KEY `Transfer_userId_importedFromId_key` (`userId`,`importedFromId`),\n'
             '  KEY `Transfer_sourceId_fkey` (`sourceId`),\n'
             '  KEY `Transfer_targetId_fkey` (`targetId`),\n'
             '  KEY `Transfer_userId_effectiveDate_id_idx` (`userId`,`effectiveDate`,`id`),\n'
             '  CONSTRAINT `Transfer_sourceId_fkey` FOREIGN KEY (`sourceId`) REFERENCES `Position` (`id`) ON DELETE '
             'CASCADE ON UPDATE CASCADE,\n'
             '  CONSTRAINT `Transfer_targetId_fkey` FOREIGN KEY (`targetId`) REFERENCES `Position` (`id`) ON DELETE '
             'CASCADE ON UPDATE CASCADE,\n'
             '  CONSTRAINT `Transfer_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE CASCADE ON '
             'UPDATE CASCADE\n'
             ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='资金往来及账户与债务的双边配对记账'",
 'Schedule': 'CREATE TABLE `Schedule` (\n'
             "  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
             "  `userId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
             "  `importedFromId` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备份来源计划标识，用于重复导入识别',\n"
             "  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '计划显示名称',\n"
             "  `operation` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作类型：expense 支出或 transfer 转账',\n"
             "  `sourceId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '支出或转出资产账户标识',\n"
             "  `targetId` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '转入账户标识；支出计划为空',\n"
             "  `amount` decimal(24,8) NOT NULL COMMENT '原币支出或转出金额',\n"
             "  `received` decimal(24,8) NOT NULL COMMENT '原币到账金额；支出计划为零',\n"
             "  `nextAt` datetime(3) NOT NULL COMMENT '下次到期业务时间对应的 UTC',\n"
             "  `intervalDays` int NOT NULL COMMENT '重复间隔天数；零表示仅执行一次',\n"
             "  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用计划',\n"
             "  `completed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '一次性计划是否已执行完毕',\n"
             "  `notes` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户备注，原文保留',\n"
             '  PRIMARY KEY (`id`),\n'
             '  UNIQUE KEY `Schedule_userId_importedFromId_key` (`userId`,`importedFromId`),\n'
             '  KEY `Schedule_userId_enabled_nextAt_idx` (`userId`,`enabled`,`nextAt`),\n'
             '  CONSTRAINT `Schedule_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE CASCADE ON '
             'UPDATE CASCADE\n'
             ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='按需执行的定时支出或转账计划'",
 'MetalPrice': 'CREATE TABLE `MetalPrice` (\n'
               "  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '唯一标识',\n"
               "  `userId` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属用户标识，用于数据隔离',\n"
               "  `metalType` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '品种：gold 黄金或 silver 白银',\n"
               "  `currency` char(3) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '价格币种',\n"
               "  `price` decimal(24,12) NOT NULL COMMENT '纯金属每克价格',\n"
               "  `date` date NOT NULL COMMENT '报价日期，UTC+8 自然日',\n"
               "  `source` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '价格来源：manual 或 goldapi',\n"
               "  `quotedAt` datetime(3) NOT NULL COMMENT '报价对应时间，UTC',\n"
               '  PRIMARY KEY (`id`),\n'
               '  UNIQUE KEY `MetalPrice_userId_metalType_currency_date_key` '
               '(`userId`,`metalType`,`currency`,`date`),\n'
               '  CONSTRAINT `MetalPrice_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User` (`id`) ON DELETE '
               'CASCADE ON UPDATE CASCADE\n'
               ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户的贵金属每克参考价历史'"}
