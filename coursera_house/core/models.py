from django.db import models


# Create your models here.
class Setting(models.Model):
    controller_name = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=100)
    value = models.IntegerField(default=20)


class Controller(models.Model):
    controller_name = models.CharField(max_length=40, unique=True)
    value = models.CharField(max_length=20, default=None, null=True)
