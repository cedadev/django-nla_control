
from django.urls import re_path
from nla_control.views import *

urlpatterns = (
    re_path(r'^api/v1/requests/(?P<req_id>\d+)', RequestView.as_view()),
    re_path(r'^api/v1/requests$', RequestView.as_view()),
    re_path(r'^api/v1/quota/(?P<user>\w+)$', QuotaView.as_view()),
    re_path(r'^api/v1/files$', TapeFileView.as_view()),
    re_path(r'unverifiedspots', unverified_spots, name='unverifiedspots')
)
