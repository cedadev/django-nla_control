
from django.conf.urls import url, include
from views import *

from rest_framework_swagger.views import get_swagger_view

schema_view = get_swagger_view(title="NLA API docs")

urlpatterns = (
    url(r'^api/v1/requests/(?P<req_id>\d+)', RequestView.as_view()),
    url(r'^api/v1/requests$', RequestView.as_view()),
    url(r'^api/v1/quota/(?P<user>\w+)$', QuotaView.as_view()),
    url(r'^api/v1/files$', TapeFileView.as_view()),
    url(r'unverifiedspots', unverified_spots, name='unverifiedspots')
)
