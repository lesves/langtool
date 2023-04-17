from django.shortcuts import render
from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Course


class CourseDetailView(DetailView):
	model = Course


class CourseListView(ListView):
	model = Course
