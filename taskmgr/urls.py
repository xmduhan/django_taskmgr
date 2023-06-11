
from django.urls import path
from . import admin

app_name = 'taskmgr'

urlpatterns = [
    path('admin/', admin.site.urls),
]