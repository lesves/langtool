#########################################
# Imports 
#########################################
# Database
from django.db import models
# Auth
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    pass


class Language(models.Model):
    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=32)
    native_name = models.CharField(max_length=32)

    def __str__(self):
        return self.name


class Course(models.Model):
	tasks = models.ManyToManyField(Task, related_name="courses")
