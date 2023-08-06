from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models


class SentenceAdmin(admin.ModelAdmin):
	readonly_fields = ["translations", "words"]


admin.site.register(models.User, UserAdmin)
admin.site.register(models.Sentence, SentenceAdmin)
admin.site.register(models.Word)
admin.site.register(models.UserWordProgress)
admin.site.register(models.Language)

# Same as in models.py, commenting out Course
#
#class CourseAdmin(admin.ModelAdmin):
#	fields = ["name", "lang", "task_number"]
#	readonly_fields = ["task_number"]
#
#	@admin.display(description="Task number")
#	def task_number(self, obj):
#		return f"{obj.tasks.count()} tasks"
#		#return obj.tasks.all()
#
#admin.site.register(models.Course, CourseAdmin)

