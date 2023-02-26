# GraphQL
import strawberry
from strawberry import auto
from strawberry.types import Info
import typing

# Auth
from django.contrib.auth import get_user_model
from strawberry.django import auth

# Models
from . import models

# Time
import datetime
from django.utils import timezone

# Other
from django.utils.html import escape


@strawberry.django.type(models.Language)
class Language:
    code: str
    name: str
    native_name: str


@strawberry.django.type(models.Sentence)
class Sentence:
    id: strawberry.ID
    lang: Language

    text: str
    audio: auto
    translations: typing.List["Sentence"]


@strawberry.django.type(models.UserTaskProgress)
class UserTaskProgress:
    id: strawberry.ID
    last_review: auto


@strawberry.django.type(models.Task)
class Task:
    id: strawberry.ID
    sentence: Sentence
    hidden: int

    correct: str
    before: str
    after: str

    @strawberry.django.field
    def prediction(self, info: Info, exact: bool = False, time: typing.Optional[datetime.datetime] = None) -> typing.Optional[float]:
        if not info.context.request.user.is_authenticated:
            return None
        if time is not None:
            time = timezone.make_aware(time)
        try:
            progress = models.UserTaskProgress.objects.get(task=self, user=info.context.request.user)
            return progress.predict(exact=exact, time=time)
        except models.UserTaskProgress.DoesNotExist:
            return None

    @strawberry.field
    def html(self) -> str:
        prev = 0
        res = []
        for i, span in enumerate(self.sentence.spans):
            res.append(self.sentence.text[prev:span[0]])
            if i == self.hidden:
                res.append(f'<input class="field" type="text" size="{int(len(self.correct)*1.3)}"/>')
            else:
                word = escape(self.sentence.text[span[0]:span[1]])
                link = f"https://kaikki.org/dictionary/{self.sentence.lang.name}/meaning/{word[:1].lower()}/{word[:2].lower()}/{word.lower()}.html"
                res.append(f'<a class="word" href="{link}" target="_blank" rel="noopener noreferrer">{word}</a>')
            prev = span[1]
        res.append(self.sentence.text[prev:])
        return "".join(res)


@strawberry.django.type(get_user_model())
class User:
    username: auto


@strawberry.type
class Query:
    me: typing.Optional[User] = auth.current_user()

    @strawberry.django.field
    def sentence(self, id: strawberry.ID) -> Sentence:
        return models.Sentence.objects.get(id=id)

    @strawberry.django.field
    def task(self, id: strawberry.ID) -> Task:
        return models.Task.objects.get(id=id)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def attempt(self, info: Info, id: strawberry.ID, success: bool) -> None:
        progress, _ = models.UserTaskProgress.objects.get_or_create(
            user=info.context.request.user,
            task=models.Task.objects.get(id=id)
        )
        progress.attempt(success)


schema = strawberry.Schema(Query, Mutation)
