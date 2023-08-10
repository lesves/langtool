# Database
from django.db import models
from django.db.models import Q, F, Count
from django.db.models.functions import TruncDay

# Storage
from django.core.files.storage import FileSystemStorage

# Auth
from django.contrib.auth.models import AbstractUser

# Time
from django.utils import timezone
from django.utils.timezone import timedelta

# Language
from nltk.tokenize import word_tokenize
from nltk.tokenize.util import align_tokens

from multilang import normalize, lemmatize

# Learning
import ebisu
import random

# Other
from django.conf import settings


def duration_to_hours(td):
    """Get hours from timedelta as float"""
    return td / timedelta(hours=1)


class Language(models.Model):
    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=32)
    native_name = models.CharField(max_length=32)

    def __str__(self):
        return self.name


class Course(models.Model):
    known = models.ForeignKey(Language, related_name="known_in", on_delete=models.CASCADE)
    learning = models.ForeignKey(Language, related_name="learning_in", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.known}-{self.learning}"


class User(AbstractUser):
    course = models.ForeignKey(Course, null=True, blank=True, related_name="learners", on_delete=models.SET_NULL)


class Word(models.Model):
    lang = models.ForeignKey(Language, on_delete=models.CASCADE, related_name="words")
    text = models.CharField(max_length=64)

    freq = models.FloatField()

    def __str__(self):
        return self.text

    class Meta:
        unique_together = [["lang", "text"]]


class FakeQuerySet:
    def __init__(self, data):
        self.data = data
        self._result_cache = []

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return FakeQuerySet(self.data[item])
        return self.data[item]


class UserWordProgressQuerySet(models.QuerySet):
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

    def order_by(self, *field_names):
        if field_names and field_names[0] in ("prediction", "-prediction"):
            return FakeQuerySet(sorted(super().order_by(*field_names[1:]), key=UserWordProgress.predict, reverse=field_names[0].startswith("-")))

        return super().order_by(*field_names)


class UserWordProgress(models.Model):
    # Basic information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="word_progress")
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="user_progress")
    last_review = models.DateTimeField(null=True, blank=True)

    # Spaced repetition parameters
    alpha = models.FloatField(default=3.0)
    beta = models.FloatField(default=3.0)
    interval = models.DurationField(null=True) # hours

    objects = UserWordProgressQuerySet.as_manager()

    def __str__(self):
        return f"{self.user}: {self.word}"

    def attempt(self, success, time=None, save=True):
        if time is None:
            time = timezone.now()

        if self.interval is None:
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
        """
        Named next_review to prevent conflicts with UserTaskProgressQuerySet.with_scheduled_review
        """
        if self.last_review is None or self.interval is None:
            return None
        return self.last_review + self.interval

    class Meta:
        verbose_name_plural = "User word progresses"


class SentenceQuerySet(models.QuerySet):
    def random(self, randint=random.randint):
        count = self.aggregate(count=Count("pk"))["count"]
        if count == 0:
            return None
        return self[randint(0, count-1)]


class Sentence(models.Model):
    lang = models.ForeignKey(Language, related_name="sentences", on_delete=models.CASCADE)

    text = models.TextField()

    link_id = models.PositiveIntegerField(null=True, blank=True, editable=False)

    audio = models.FileField(storage=FileSystemStorage(location="data", base_url="/data"), null=True, blank=True)
    translations = models.ManyToManyField("Sentence", blank=True, related_name="translation_of")

    words = models.ManyToManyField(Word, blank=True, related_name="sentences")

    objects = SentenceQuerySet.as_manager()

    def __str__(self):
        return self.text

    @property
    def tokens(self):
        return word_tokenize(self.text, self.lang.name.lower())

    @property
    def lemmas(self):
        return [lemmatize(t, self.lang.code) for t in self.tokens]

    @property
    def spans(self):
        try:
            return align_tokens(self.tokens, self.text)
        except ValueError:
            return align_tokens([tok.replace("''", "\"").replace("``", "\"") for tok in self.tokens], self.text)
