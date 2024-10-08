from django.urls import path
from . import views
#from . import signup 
app_name = 'home'
urlpatterns=[
    path('',views.homes_list,name="homes_list"),
   # path('pages/',views.pages_list,name="pages_list"),
  
      

]