ingestion/
    __init__.py
    apps.py
    models.py
    admin.py

    handlers/
        __init__.py
        admin.py            # 管理员触发抓取
        telegram.py         # Telegram 相关抓取入口（按钮、命令）

    services/
        __init__.py
        fetcher.py          # 负责从 Telegram / API 拉取原始数据
        parser.py           # 负责解析原始消息 → 标准化结构
        normalizer.py       # 负责把解析后的数据转换成内部格式
        saver.py            # 负责保存到 Report / tgusers / 其他模型
        dispatcher.py       # 根据来源类型自动选择 parser + saver

    pipelines/
        __init__.py
        telegram_report_pipeline.py   # Telegram → Report
        telegram_user_pipeline.py     # Telegram → tgusers
        external_api_pipeline.py      # 外部 API → 内部模型（未来扩展）

    utils/
        __init__.py
        telegram_client.py   # Telegram Bot API / MTProto 客户端
        text_cleaner.py      # 文本清洗
        time_utils.py        # 时间处理

    constants.py
