from places.models import Place, PlaceFormerName
from django.db.models import Q
# ============================
# 1. 场所查找
# ============================

def find_place_by_name(query_name: str):
    """根据 name / short_name / first_letter 或曾用名查找 Place"""
    place = Place.objects.filter(
        Q(name=query_name) |
        Q(short_name=query_name) |
        Q(first_letter=query_name)
    ).first()

    if place:
        return place

    former = PlaceFormerName.objects.filter(
        Q(name=query_name) |
        Q(short_name=query_name) |
        Q(first_letter=query_name)
    ).first()

    if former:
        return former.place

    return None


def get_all_place_names(place: Place):
    """获取场所所有可匹配名称（含曾用名）"""
    names = set()

    # 主名称
    if place.name:
        names.add(place.name)
    if place.short_name:
        names.add(place.short_name)
    if place.first_letter:
        names.add(place.first_letter)

    # 曾用名
    for fn in place.former_names.all():
        if fn.name:
            names.add(fn.name)
        if fn.short_name:
            names.add(fn.short_name)
        if fn.first_letter:
            names.add(fn.first_letter)

    return list(names)
