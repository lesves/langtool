# GraphQL
import strawberry
from strawberry import auto
from strawberry.types import Info
import typing

# Auth
from django.contrib.auth import get_user_model
from strawberry.django import auth

# Models
from django.db.models import Exists, OuterRef
from . import models

# Time
import datetime
from django.utils import timezone

# Other
from django.utils.html import escape
import functools


#######################
# Language            #
#######################


@strawberry.django.type(models.Language)
class Language:
    code: str
    name: str
    native_name: str


@strawberry.django.filters.filter(models.Language)
class LanguageFilter:
    code: auto
    name: auto
    native_name: auto


#######################
# Sentence            #
#######################


@strawberry.django.type(models.Sentence)
class Sentence:
    id: strawberry.ID
    lang: Language

    text: str
    audio: auto
    translations: typing.List["Sentence"]


@strawberry.django.filters.filter(models.Sentence)
class SentenceFilter:
    id: auto

    text: strawberry.django.filters.FilterLookup[str]
    lang: LanguageFilter

    audio: strawberry.django.filters.FilterLookup[str]
    translations: "SentenceFilter"

    has_audio: typing.Optional[bool]

    def filter_has_audio(self, queryset):
        if queryset.model != models.Sentence:
            # Fix flaw in django strawberry integration
            # When sentence is the related object, the filter fails

            if queryset.model == models.Task:
                key = "sentence__in"
            elif queryset.model == models.UserTaskProgress:
                key = "task__sentence__in"
            else:
                raise NotImplementedError
            return queryset.filter(
                **{key: self.filter_has_audio(models.Sentence.objects.all())}
            )

        if self.has_audio is None:
            pass
        elif self.has_audio:
            queryset = queryset.exclude(audio="")
        else:
            queryset = queryset.filter(audio="")

        return queryset


#######################
# Task                #
#######################


@strawberry.django.type(models.Task)
class Task:
    id: strawberry.ID
    sentence: Sentence
    hidden: int

    correct: str
    before: str
    after: str


    @strawberry.django.field
    def progress(self, info: Info) -> typing.Optional["UserTaskProgress"]:
        if not info.context.request.user.is_authenticated:
            return None
        return models.UserTaskProgress.objects.filter(task=self, user=info.context.request.user).first()


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


@strawberry.django.filters.filter(models.Task)
class TaskFilter:
    id: auto
    hidden: auto
    sentence: SentenceFilter

    new: typing.Optional[bool] = None

    def filter_new(self, queryset, info: Info):
        if self.new is not None:
            if not info.context.request.user.is_authenticated:
                return None

            query = Exists(
                    models.UserTaskProgress.objects.filter(
                        task=OuterRef("pk"),
                        user=info.context.request.user
                    )
                )

            if self.new:
                query = ~query
            queryset = queryset.filter(query)

        return queryset


#######################
# User                #
#######################


@strawberry.django.type(get_user_model())
class User:
    username: auto


#######################
# UserTaskProgress    #
#######################


@strawberry.django.type(models.UserTaskProgress)
class UserTaskProgress:
    id: strawberry.ID
    task: Task
    user: User
    last_review: datetime.datetime
    scheduled_review: datetime.datetime

    @strawberry.django.field
    def prediction(self, exact: bool = False, time: typing.Optional[datetime.datetime] = None) -> typing.Optional[float]:
        if time is not None:
            time = timezone.make_aware(time)
        return self.predict(exact=exact, time=time)


@strawberry.django.ordering.order(models.UserTaskProgress)
class UserTaskProgressOrder:
    last_review: auto
    scheduled_review: auto
    prediction: auto


@strawberry.django.filters.filter(models.UserTaskProgress)
class UserTaskProgressFilter:
    task: TaskFilter

    last_review: strawberry.django.filters.FilterLookup[datetime.datetime]
    scheduled_review: strawberry.django.filters.FilterLookup[datetime.datetime]

    def filter_scheduled_review(self, queryset):
        filter_kwargs, _ = strawberry.django.filters.build_filter_kwargs(self.next_review)
        return queryset.with_scheduled_review().filter(
            **{f"scheduled_review__{k}": v for k, v in filter_kwargs.items()}
        )


#######################
# Field Utils         #
#######################


def processed_field(pre_hooks, post_hooks, **kwargs):
    field = strawberry.django.field(**kwargs)
    original = field.get_queryset

    @functools.wraps(original)
    def get_queryset(queryset, info: Info, **kwargs):
        for pre in pre_hooks:
            queryset = pre(queryset, info, **kwargs)
        queryset = original(queryset, info, **kwargs)
        for post in post_hooks:
            queryset = post(queryset, info, **kwargs)
        return queryset

    field.get_queryset = get_queryset
    return field


def filter_user(queryset, info, **kwargs):
    if info.context.request.user.is_authenticated:
        return queryset.filter(user=info.context.request.user)
    return models.UserTaskProgress.objects.none()


def order_prediction_pre(queryset, info, order=None, **kwargs):
    if order and order.prediction:
        order._prediction_order = order.prediction
        order.prediction = strawberry.UNSET
    return queryset


def order_prediction_post(queryset, info, order=None, **kwargs):
    if order and hasattr(order, "_prediction_order"):
        return sorted(list(queryset), key=models.UserTaskProgress.predict, reverse=order._prediction_order == strawberry.django.ordering.Ordering.DESC)
    return queryset


#######################
# Query & Mutation    #
#######################


@strawberry.type
class Query:
    me: typing.Optional[User] = auth.current_user()

    sentences: typing.List[Sentence] = strawberry.django.field(filters=SentenceFilter, pagination=True)
    tasks: typing.Optional[typing.List[Task]] = strawberry.django.field(filters=TaskFilter, pagination=True)

    progresses: typing.List[UserTaskProgress] = processed_field(
        [filter_user, order_prediction_pre], 
        [order_prediction_post],
        filters=UserTaskProgressFilter, 
        order=UserTaskProgressOrder,
        pagination=True,
    )

    @strawberry.django.field
    def sentence(self, id: strawberry.ID) -> Sentence:
        return models.Sentence.objects.get(id=id)

    @strawberry.django.field
    def task(self, id: strawberry.ID) -> Task:
        return models.Task.objects.get(id=id)

    @strawberry.django.field
    def progress(self, id: strawberry.ID) -> Task:
        return models.UserTaskProgress.objects.get(id=id)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def attempt(self, info: Info, id: strawberry.ID, success: bool) -> UserTaskProgress:
        progress, _ = models.UserTaskProgress.objects.get_or_create(
            user=info.context.request.user,
            task=models.Task.objects.get(id=id)
        )
        progress.attempt(success)
        return progress


schema = strawberry.Schema(Query, Mutation)
