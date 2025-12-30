# collect/management/commands/import_staff_csv.py
"""
## CSV 文件格式（示例）
place_name,nickname,birth_year,bust_size,bust_info,attractiveness,extra_info
金园,999,98年左右,C,软，略微下垂，胸型好看,御姐型 7分,服务好 很听话 很骚
金园,888,00年左右,D,软,甜美型 8分,服务好

## 运行命令
python manage.py import_staff_csv staff_list.csv

"""
import csv
from django.core.management.base import BaseCommand
from places.models import Place, Staff
from collect.models import Submission


class Command(BaseCommand):
    help = "从 CSV 文件批量导入技师信息"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="CSV 文件路径")

    def handle(self, *args, **options):
        csv_path = options["csv_path"]

        created_staff_count = 0
        updated_staff_count = 0
        submission_count = 0

        self.stdout.write(self.style.WARNING(f"开始导入 CSV: {csv_path}"))

        try:
            with open(csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    place_name = row.get("place_name") or row.get("会所名称")
                    nickname = row.get("nickname") or row.get("技师号码")

                    if not place_name or not nickname:
                        self.stdout.write(self.style.ERROR(f"跳过无效行: {row}"))
                        continue

                    # 获取或创建 Place
                    place, _ = Place.objects.get_or_create(name=place_name)

                    # 获取或创建 Staff
                    staff, created = Staff.objects.get_or_create(
                        place=place,
                        nickname=nickname,
                        defaults={"is_active": True}
                    )

                    if created:
                        created_staff_count += 1
                    else:
                        updated_staff_count += 1

                    # 创建 Submission（档案来源）
                    Submission.objects.create(
                        staff=staff,
                        nickname=nickname,
                        birth_year=row.get("birth_year") or row.get("出生年份"),
                        bust_size=row.get("bust_size") or row.get("胸围大小"),
                        bust_info=row.get("bust_info") or row.get("胸围信息"),
                        attractiveness=row.get("attractiveness") or row.get("颜值信息"),
                        extra_info=row.get("extra_info") or row.get("其他信息"),
                        status="approved",
                    )

                    submission_count += 1

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("❌ CSV 文件不存在"))
            return

        self.stdout.write(self.style.SUCCESS("导入完成！"))
        self.stdout.write(self.style.SUCCESS(f"新增技师: {created_staff_count}"))
        self.stdout.write(self.style.SUCCESS(f"更新技师: {updated_staff_count}"))
        self.stdout.write(self.style.SUCCESS(f"创建档案: {submission_count}"))
