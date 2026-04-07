from .common import pre_process_user

@pre_process_user
def group_message_preprocessor(update, context):
    # 什么都不做，只是触发 pre_process_user
    return
