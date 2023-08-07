# GraphQL
import strawberry
from strawberry import auto
from strawberry.types import Info
import typing

import strawberry_django
from strawberry_django.optimizer import DjangoOptimizerExtension

# Auth
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from strawberry.django import auth

from langtool.jwtauth import issue_jwt_token

# Models
from django.db.models import Exists, OuterRef
from . import models

# Time
import datetime
from django.utils import timezone

# Other
from django.conf import settings
from django.utils.html import escape
import functools


#######################
# Language            #
#######################


@strawberry.django.filters.filter(models.Language)
class LanguageFilter:
    code: auto
    name: auto
    native_name: auto


@strawberry.django.type(models.Language, filters=LanguageFilter)
class Language:
    code: str
    name: str
    native_name: str


#######################
# Course              #
#######################


@strawberry.django.type(models.Course)
class Course:
    id: strawberry.ID

    known: Language
    learning: Language


#######################
# Sentence            #
#######################


@strawberry.django.ordering.order(models.Sentence)
class SentenceOrder:
    text: auto


@strawberry.django.filters.filter(models.Sentence)
class SentenceFilter:
    id: auto

    text: typing.Optional[strawberry.django.filters.FilterLookup[str]]
    lang: typing.Optional[LanguageFilter]

    audio: typing.Optional[strawberry.django.filters.FilterLookup[str]]
    translations: typing.Optional["SentenceFilter"]

    words: typing.Optional["WordFilter"]

    has_audio: typing.Optional[bool]

    def filter_has_audio(self, queryset):
        if self.has_audio is None:
            pass
        elif self.has_audio:
            queryset = queryset.exclude(audio="")
        else:
            queryset = queryset.filter(audio="")

        return queryset


@strawberry.django.type(models.Sentence, order=SentenceOrder, filters=SentenceFilter)
class Sentence:
    id: strawberry.ID
    lang: Language

    text: str
    audio: typing.Optional[strawberry.django.DjangoFileType]
    translations: typing.List["Sentence"]

    words: typing.List["Word"]

    tokens: typing.List[str]
    lemmas: typing.List[str]
    spans: typing.List[typing.Tuple[int, int]]

    @strawberry.django.field
    def audio(self):
        if not self.audio:
            return None
        return self.audio


#######################
# Word                #
#######################


@strawberry.django.ordering.order(models.Word)
class WordOrder:
    text: auto
    freq: auto


@strawberry.django.filters.filter(models.Word)
class WordFilter:
    lang: typing.Optional[LanguageFilter]
    text: typing.Optional[strawberry.django.filters.FilterLookup[str]]
    freq: typing.Optional[strawberry.django.filters.FilterLookup[float]]

    progress: typing.Optional["UserWordProgressFilter"]

    new: typing.Optional[bool]
    only_used: bool = True

    def filter_new(self, queryset, info: Info):
        if self.new is not None:
            if not info.context.request.user.is_authenticated:
                return models.Word.objects.none()

            query = Exists(
                    models.UserWordProgress.objects.filter(
                        word=OuterRef("pk"),
                        user=info.context.request.user
                    )
                )

            if self.new:
                query = ~query
            queryset = queryset.filter(query)

        return queryset

    def filter_only_used(self, queryset):
        if queryset.model != models.Word:
            # Fix flaw in django strawberry integration
            # When sentence is the related object, the filter fails

            if queryset.model == models.UserWordProgress:
                key = "word__in"
            else:
                raise NotImplementedError
            return queryset.filter(
                **{key: self.filter_only_used(models.Word.objects.all())}
            )

        if self.only_used:
            queryset = queryset.exclude(sentences__isnull=True)
        return queryset


@strawberry.django.type(models.Word, filters=WordFilter, order=WordOrder)
class Word:
    id: auto
    lang: Language
    text: str
    freq: float

    sentences: typing.List["Sentence"] = strawberry.django.field(pagination=True)

    @strawberry.django.field
    def random_sentence(self, info: Info, filters: typing.Optional[SentenceFilter] = strawberry.UNSET) -> typing.Optional[Sentence]:
        qs = self.sentences
        if filters is not strawberry.UNSET:
            qs = strawberry_django.filters.apply(filters, qs, info)
        return qs.random()

    @strawberry.django.field(pagination=True)
    def progress(self, info: Info) -> typing.Optional["UserWordProgress"]:
        if not info.context.request.user.is_authenticated:
            return models.UserWordProgress.objects.none()
        return models.UserWordProgress.objects.filter(word=self, user=info.context.request.user).first()


#######################
# User                #
#######################


@strawberry.django.type(get_user_model())
class User:
    username: auto
    course: typing.Optional[Course]


@strawberry.django.input(get_user_model())
class UserRegistrationInput:
    username: auto
    password1: str
    password2: str


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ("username",)


#######################
# UserWordProgress    #
#######################


@strawberry.django.ordering.order(models.UserWordProgress)
class UserWordProgressOrder:
    last_review: auto
    scheduled_review: auto
    prediction: auto


@strawberry.django.filters.filter(models.UserWordProgress)
class UserWordProgressFilter:
    word: typing.Optional[WordFilter]

    last_review: typing.Optional[strawberry.django.filters.FilterLookup[datetime.datetime]]
    scheduled_review: typing.Optional[strawberry.django.filters.FilterLookup[datetime.datetime]]

    def filter_scheduled_review(self, queryset):
        filter_kwargs, _ = strawberry.django.filters.build_filter_kwargs(self.scheduled_review)
        return queryset.with_scheduled_review().filter(
            **{f"scheduled_review__{k}": v for k, v in filter_kwargs.children}
        )


@strawberry.django.type(models.UserWordProgress, filters=UserWordProgressFilter, order=UserWordProgressOrder)
class UserWordProgress:
    id: strawberry.ID
    word: Word
    user: User
    last_review: datetime.datetime
    scheduled_review: datetime.datetime

    @strawberry.django.field
    def prediction(self, exact: bool = False, time: typing.Optional[datetime.datetime] = None) -> typing.Optional[float]:
        if time is not None:
            time = timezone.make_aware(time)
        return self.predict(exact=exact, time=time)


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
    return models.UserWordProgress.objects.none()


def add_scheduled_review(queryset, info, **kwargs):
    return queryset.with_scheduled_review()


#######################
# Query & Mutation    #
#######################


@strawberry.type
class Query:
    me: typing.Optional[User] = auth.current_user()

    courses: typing.List[Course] = strawberry.django.field()
    languages: typing.List[Language] = strawberry.django.field()
    sentences: typing.List[Sentence] = strawberry.django.field(pagination=True)
    words: typing.Optional[typing.List[Word]] = strawberry.django.field(pagination=True)

    progresses: typing.List[UserWordProgress] = processed_field(
        [filter_user, add_scheduled_review], 
        [],
        pagination=True,
    )

    @strawberry.django.field
    def sentence(self, id: strawberry.ID) -> Sentence:
        return models.Sentence.objects.get(id=id)

    @strawberry.django.field
    def word(self, id: strawberry.ID) -> Word:
        return models.Word.objects.get(id=id)

    @strawberry.django.field
    def progress(self, id: strawberry.ID) -> UserWordProgress:
        return models.UserWordProgress.objects.get(id=id)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def attempt(self, info: Info, id: strawberry.ID, success: bool) -> UserWordProgress:
        progress, _ = models.UserWordProgress.objects.get_or_create(
            user=info.context.request.user,
            word=models.Word.objects.get(id=id)
        )
        progress.attempt(success)
        return progress

    # JWT auth

    @strawberry.mutation
    def token_auth(self, username: str, password: str) -> typing.Optional[str]:
        return issue_jwt_token(username, password)

    # Classic login
    login: typing.Optional[User] = auth.login()
    logout = auth.logout()

    @strawberry.mutation
    def register(self, data: UserRegistrationInput) -> typing.Optional[User]:
        form = CustomUserCreationForm(strawberry.asdict(data))
        if form.is_valid():
            return form.save()
        else:
            raise Exception(form.errors.popitem()[1][0])

    @strawberry.mutation
    def set_course(self, info: Info, course_id: strawberry.ID) -> typing.Optional[User]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None

        user.course = models.Course.objects.get(id=course_id)
        user.save()
        
        return user


schema = strawberry.Schema(
    Query,
    Mutation,
    extensions=[
        DjangoOptimizerExtension,
    ]
)
