from django.urls import path

from strawberry.django.views import GraphQLView
from .api import schema

from . import views


urlpatterns = [
	path("", views.CourseListView.as_view(), name="courses"),
	path("course/<int:pk>/", views.CourseDetailView.as_view(), name="course"),

	path("graphql/", GraphQLView.as_view(schema=schema), name="graphql"),
]
