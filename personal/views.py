from django.shortcuts import render
from django.template import context


def home(request, *args, **kwargs):
    context = {'name': 'Gozon'}

    return render(request, 'personal/home.html', context)
