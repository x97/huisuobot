
import re
from typing import Dict, Optional,List
from telethon.tl.custom import Message  # 视你的导入路径而定

from ingestion.constants import REPORT_TEMPLATE

# ============================
# 🔥 1. 字段别名映射（可扩展）
# ============================
FIELD_ALIASES = {
    "会所名称": ["会所名称", "会所/老师"],
    "技师号码": ["技师号码", "老师艺名", "老师花名", "佳人名称", "老师名字", "老师名称", "老师号码"],
    "会所位置": ["会所位置", "所在位置", ],
    "会所价格": ["会所价格", "上课价位"],
    "验证留名": ["验证留名", "工兵留名", "出击用户", "学生留名", "出击留名"],
    "验证时间": ["验证时间", "探访时间", "出击时间"],

    "颜值评价": ["颜值评价", "颜值身材", "颜值分数",],
    "身材评价": ["身材评价", "身材分数"],

    "推荐程度": ["推荐程度", "满意程度", "推荐分数",],

    # 出击详情类字段（你会配置多个）
    "出击详情": ["服务内容", "服务态度", "优点缺点", "出击详情", "体验细节", "出击体验",
                 "推荐理由", "服务详情"],
}

# ============================
# 🔥 2. 结束标记（遇到这些就截断）
# ============================
END_MARKERS = [
    "【", "报告完全属", "报告仅供参考", "温馨提示", "✨", "✍️", "♥️",
    "注：", "👉", "（提交报告", "更多详情"
]

def remove_usernames(text: str) -> str:
    """
    删除 Telegram 用户名，例如 @abc123 @bot_name
    不删除邮箱地址。
    """
    # 删除 @username（字母数字下划线）
    text = re.sub(r"(?<!\w)@[A-Za-z0-9_]{3,32}", "", text)

    # 删除多余空格
    text = re.sub(r"\s{2,}", " ", text)

    # 删除多余空行
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()

# ============================
# 🔥 3. 清洗文本（去广告、去 emoji、去链接）
# ============================
def clean_text(text: str) -> str:
    # 删除 Telegram 用户名
    text = remove_usernames(text)

    # 删除链接
    text = re.sub(r"https?://\S+", "", text)

    # 删除 emoji（简单版）
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)

    # 删除多余空行
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()



# ============================
# 🔥 4. 提取单字段（支持跨行 + 截断）
# ============================
def extract_single_field(text: str, aliases: List[str]) -> str:
    for field in aliases:
        # 匹配字段名（支持：冒号、空格、换行）
        pattern = rf"(?:【{field}】|{field})[:：]?\s*(.*)"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            continue

        content = match.group(1).strip()

        # 遇到 END_MARKERS 截断
        for marker in END_MARKERS:
            idx = content.find(marker)
            if idx != -1:
                content = content[:idx].strip()

        # 去掉多余空行
        content = re.sub(r"\n{2,}", "\n", content)

        return content.strip()

    return ""


# ============================
# 🔥 5. 专业级字段提取器（支持多字段合并）
# ============================
def extract_fields_v2(text: str) -> Dict[str, str]:
    text = clean_text(text)

    result = {}

    for canonical, aliases in FIELD_ALIASES.items():

        # 特殊处理：出击详情（多个字段合并）
        if canonical == "出击详情":
            merged = []
            for alias in aliases:
                value = extract_single_field(text, [alias])
                if value and value not in merged:
                    merged.append(value)

            result[canonical] = "\n".join(merged).strip()
            continue

        # 普通字段
        result[canonical] = extract_single_field(text, aliases)

    return result


def parse_report(msg: Message) -> Optional[Dict[str, str]]:
    """
    把抓取到的报告信息转化成模板信息。
    如果字段为空超过 3 个，则认为不是有效报告，返回 None。
    """

    # 1. 取出文本内容（Telethon 里通常是 .message 或 .text）
    text = msg.message or ""   # 或者 msg.text，看你之前怎么用的

    fields = extract_fields_v2(text)

    # 2. 统计空字段数量
    empty_count = sum(1 for v in fields.values() if not v)

    if empty_count > 3:
        return None

    # 3. 格式化模板
    report_text = REPORT_TEMPLATE.format(**fields)

    # 4. 返回结构里顺便带上发布时间
    return {
        "content": report_text,
        "place_name": fields.get("会所名称"),
        "published_at": msg.date,  # 这里把 Telethon 的发布时间带出来
    }

