# interactions/utils.py

from django.conf import settings

TEMPLATE_FIELDS = {
    "🏡场所名称": "place_name",
    "🔢技师号码": "nickname",
    "🎂出生年份": "birth_year",
    "💗胸围大小": "bust_size",
    "💗胸围信息": "bust_info",
    "😍颜值信息": "attractiveness",
    "📝其他信息": "extra_info",
}


def render_submission(submission):
    staff = submission.staff
    place = staff.place

    lines = ["【技师信息】\n"]
    for label, field in TEMPLATE_FIELDS.items():
        value = getattr(submission, field, None)
        if value:
            lines.append(f"{label}：{value}")

    lines.append("\n【所属场所】")
    lines.append(f"{place.name}-{place.district}-{place.city}")

    lines.append("\n📅提交时间:")
    lines.append(submission.created_at.strftime("%Y-%m-%d %H:%M"))

    return "\n".join(lines)


def get_submission_page(submissions, page):
    index = page - 1
    return submissions[index]
