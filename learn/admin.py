from django.contrib import admin

from . import models


admin.site.register(models.Sentence)
admin.site.register(models.Task)
admin.site.register(models.UserTaskProgress)
admin.site.register(models.Course)
admin.site.register(models.Language)
