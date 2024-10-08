from django.shortcuts import render
from django.http import HttpResponse, HttpResponseNotFound
# Create your views here.
def homes_list(request):
    return render (request,'home/index.html')

def pages_list(request):
    return HttpResponse("<h1>Page was found</h1>")