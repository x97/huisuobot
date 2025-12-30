# interactions/keyboards.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from interactions.services import count_votes, count_reports

def build_submission_keyboard(submission, staff, user_id=None):
    """
    通用投稿交互键盘：只包含点赞 / 点踩 / 离职反馈
    不包含分页按钮
    """
    likes, dislikes = count_votes(submission)
    reports = count_reports(staff)

    # 判断当前用户是否点赞/点踩
    user_vote = None
    if user_id:
        from interactions.models import SubmissionVote
        vote = SubmissionVote.objects.filter(submission=submission, user_id=user_id).first()
        if vote:
            user_vote = vote.vote

    # 判断当前用户是否反馈过离职
    user_reported = False
    if user_id:
        from interactions.models import StaffInactiveReport
        user_reported = StaffInactiveReport.objects.filter(staff=staff, user_id=user_id).exists()

    like_text = f"点赞👍🏻({likes})" if user_vote != 1 else f"已点赞👍🏻({likes})"
    dislike_text = f"踩👎🏻({dislikes})" if user_vote != -1 else f"已踩👎🏻({dislikes})"
    inactive_text = f"反馈该技师已离职({reports})" if not user_reported else f"已反馈离职({reports})"

    buttons = [
        [
            InlineKeyboardButton(like_text, callback_data=f"sub:like:{submission.id}"),
            InlineKeyboardButton(dislike_text, callback_data=f"sub:dislike:{submission.id}"),
        ],
        [
            InlineKeyboardButton(inactive_text, callback_data=f"sub:inactive:{staff.id}")
        ]
    ]

    return InlineKeyboardMarkup(buttons)
