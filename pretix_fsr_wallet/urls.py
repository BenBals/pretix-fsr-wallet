from django.conf.urls import url
from django.urls import include, path
from pretix.multidomain import event_url

from .views import OIDCLoginReturnView

urlpatterns = [
    path('wallet/', include([
        path('return/', OIDCLoginReturnView.as_view(), name='oidc_login_return'),
    ])),
]
