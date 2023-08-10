from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models


class CustomUserAdmin(UserAdmin):
    fieldsets = list(UserAdmin.fieldsets) + [
        ("Course information", {"fields": ["course"]})
    ]


class SentenceAdmin(admin.ModelAdmin):
    list_display = ["text", "lang"]
    readonly_fields = ["translations", "words"]
    list_filter = ["lang"]


class WordAdmin(admin.ModelAdmin):
    list_display = ["text", "lang", "freq", "number_of_sentences"]
    readonly_fields = ["used_in_sentences"]
    list_filter = ["lang"]

    def number_of_sentences(self, obj):
        return obj.sentences.count()

    def used_in_sentences(self, obj):
        return "\n".join((str(s) for s in obj.sentences.all()))


admin.site.register(models.User, CustomUserAdmin)
admin.site.register(models.Sentence, SentenceAdmin)
admin.site.register(models.Word, WordAdmin)
admin.site.register(models.UserWordProgress)
admin.site.register(models.Language)
admin.site.register(models.Course)

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

