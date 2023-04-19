from django.contrib import admin

from . import models


admin.site.register(models.Sentence)
admin.site.register(models.Task)
admin.site.register(models.UserTaskProgress)
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

