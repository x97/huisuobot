# interactions/models.py

from django.db import models
from collect.models import Submission
from places.models import Staff


class SubmissionVote(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    user_id = models.BigIntegerField()
    vote = models.SmallIntegerField()  # 1=like, -1=dislike
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("submission", "user_id")


class StaffInactiveReport(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    user_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("staff", "user_id")
