from django.urls import include, path

from .views import OIDCLoginReturnView

urlpatterns = [
    path(
        "wallet/",
        include(
            [
                path("return/", OIDCLoginReturnView.as_view(), name="oidc_login_return"),
            ]
        ),
    ),
]
