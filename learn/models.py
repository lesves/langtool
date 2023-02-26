# Database
from django.db import models
from django.db.models import Q, F, Count
from django.db.models.functions import TruncDay

# Storage
from django.core.files.storage import FileSystemStorage

# Auth
from django.contrib.auth.models import AbstractUser

# Language
from nltk.tokenize import word_tokenize
from nltk.tokenize.util import align_tokens
from wordfreq import word_frequency

# Learning
import ebisu

# Other
from django.conf import settings
from django.utils.html import escape


class Language(models.Model):
    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=32)
    native_name = models.CharField(max_length=32)

    def __str__(self):
        return self.name


class User(AbstractUser):
    languages = models.ManyToManyField(Language, related_name="speakers")


class Sentence(models.Model):
    lang = models.ForeignKey(Language, related_name="sentences", on_delete=models.CASCADE)

    text = models.TextField()

    audio = models.FileField(storage=FileSystemStorage(location="data", base_url="/data"), null=True, blank=True)
    translations = models.ManyToManyField("Sentence", blank=True, related_name="translation_of")

    def __str__(self):
        return self.text

    @property
    def tokens(self):
        return word_tokenize(self.text, self.lang.name)

    @property
    def spans(self):
        try:
            return align_tokens(self.tokens, self.text)
        except ValueError:
            return align_tokens([tok.replace("''", "\"").replace("``", "\"") for tok in self.tokens], self.text)


class TaskQuerySet(models.QuerySet):
    def random(self, n):
        count = self.aggregate(count=Count("pk"))["count"]
        return [self[random.randint(0, count-1)] for _ in range(n)]


class Task(models.Model):
    sentence = models.ForeignKey(Sentence, on_delete=models.CASCADE, related_name="tasks")
    hidden = models.PositiveSmallIntegerField()

    @property
    def before(self):
        return self.sentence.text[:self.sentence.spans[self.hidden][0]]

    @property
    def after(self):
        return self.sentence.text[self.sentence.spans[self.hidden][1]:]


class UserTaskProgressQuerySet(models.QuerySet):
    def with_scheduled_review(self):
        return self.annotate(scheduled_review=models.ExpressionWrapper(
                F("last_review") + F("interval"),
                output_field=models.DateTimeField()
            ))

    def with_scheduled_day(self):
        return self.annotate(scheduled_day=models.ExpressionWrapper(
                TruncDay(F("last_review") + F("interval")),
                output_field=models.DateTimeField()
            ))


class UserTaskProgress(models.Model):
    # Basic information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="task_progress")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="user_progress")
    last_review = models.DateTimeField(auto_now=True)

    # Spaced repetition parameters
    alpha = models.FloatField(default=3.0)
    beta = models.FloatField(default=3.0)
    interval = models.DurationField(null=True) # hours

    def attempt(self, success, time=None, save=True):
        if time is None:
            time = timezone.now()

        if self.last_review is None:
            self.interval = timedelta(hours=settings.INITIAL_INTERVAL[success])
        else:
            model = (self.alpha, self.beta, duration_to_hours(self.interval))

            elapsed = duration_to_hours(time-self.last_review)
            new_model = ebisu.updateRecall(model, success, 1, elapsed)

            self.alpha = new_model[0]
            self.beta = new_model[1]
            self.interval = timedelta(hours=new_model[2])

        self.last_review = time
        if save:
            self.save()

    def predict(self, time=None, exact=False):
        if self.last_review is None or self.interval is None:
            if exact:
                return 0.
            else:
                return float("-inf")

        if time is None:
            time = timezone.now()

        elapsed = duration_to_hours(time-self.last_review)
        model = (self.alpha, self.beta, duration_to_hours(self.interval))
        return ebisu.predictRecall(model, elapsed, exact=exact)

    @property
    def next_review(self):
        if self.last_review is None or self.interval is None:
            return None
        return self.last_review + self.interval


class Course(models.Model):
    language = models.ForeignKey(Language, related_name="courses", on_delete=models.CASCADE)
    tasks = models.ManyToManyField(Task, related_name="courses")
