# common/utils.py
"""masking 工具 用于把 phone/wechat 打码显示"""
from telegram.ext import CallbackContext
from telegram.ext import  ConversationHandler

def mask_phone(phone: str) -> str:
    if not phone:
        return ""
    # 保留前3后3，中间打星
    if len(phone) <= 6:
        return phone[:1] + "****" + phone[-1:]
    return phone[:3] + "****" + phone[-3:]

def mask_wechat(wechat: str) -> str:
    if not wechat:
        return ""
    # 保留前2后3，中间打星
    if len(wechat) <= 5:
        return wechat[:1] + "****" + wechat[-1:]
    return wechat[:2] + "****" + wechat[-3:]

def end_all_conversations(context: CallbackContext):
    """强制清空所有对话状态（关键：清理 user_data 和 conversation_state）"""
    # 清空用户会话数据
    context.user_data.clear()
    # 清空对话状态（关键！解决状态残留）
    if context.chat_data:
        context.chat_data.pop('conversation_state', None)
    # 也可以直接调用 ConversationHandler 的结束逻辑（如果有全局引用）
    return ConversationHandler.END