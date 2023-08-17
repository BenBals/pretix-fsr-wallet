from django.urls import include, path

from .views import OIDCLoginReturnView

organizer_patterns = [
    path(
        "wallet/",
        include(
            [
                path(
                    "return/", OIDCLoginReturnView.as_view(), name="oidc_login_return"
                ),
            ]
        ),
    ),
]
