# interactions/services.py

from interactions.models import SubmissionVote, StaffInactiveReport

def handle_like(submission, user_id):
    vote, created = SubmissionVote.objects.get_or_create(
        submission=submission,
        user_id=user_id,
        defaults={"vote": 1}
    )

    # 如果是第一次点赞 → created=True → 返回 True
    if created:
        return True

    # 如果之前点过赞 → vote.vote == 1 → 重复操作
    if vote.vote == 1:
        return False

    # 如果之前点过踩 → 改成赞
    vote.vote = 1
    vote.save()
    return True

def handle_dislike(submission, user_id):
    vote, created = SubmissionVote.objects.get_or_create(
        submission=submission,
        user_id=user_id,
        defaults={"vote": -1}
    )

    if created:
        return True

    if vote.vote == -1:
        return False

    vote.vote = -1
    vote.save()
    return True


def handle_inactive_report(staff, user_id):
    report, created = StaffInactiveReport.objects.get_or_create(
        staff=staff,
        user_id=user_id
    )
    return created  # True = 第一次举报，False = 重复举报



def count_votes(submission):
    likes = SubmissionVote.objects.filter(submission=submission, vote=1).count()
    dislikes = SubmissionVote.objects.filter(submission=submission, vote=-1).count()
    return likes, dislikes


def count_reports(staff):
    return StaffInactiveReport.objects.filter(staff=staff).count()
