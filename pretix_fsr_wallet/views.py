import json
import logging
import re
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _, gettext_noop
from django.views.generic import FormView, TemplateView
from django.views import View
from i18nfield.forms import I18nFormField, I18nTextInput
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder
from pretix.base.models import Event, Question
from pretix.control.views.event import EventSettingsViewMixin
from django.http import HttpResponse

import pretix_fsr_wallet.signals as signals

logger = logging.getLogger(__name__)


def valid_regex(val):
    try:
        re.compile(val)
    except re.error:
        raise ValidationError(_("Not a valid Python regular expression."))


class FsrWalletSettingsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.obj = kwargs.pop("obj")
        super().__init__(*args, **kwargs)

        self.fields["wallet_backend:url"] = forms.CharField(
            label="Wallet Backend URL",
            initial=signals.default_config['wallet_backend:url'],
            required=True,
        )

        self.fields["wallet_backend:api_key"] = forms.CharField(
            label="Wallet Backend API Key",
            required=True,
        )

        self.fields["oidc:url"] = forms.CharField(
            label="OIDC URL",
            initial=signals.default_config['oidc:url'],
            required=True,
        )

        self.fields["oidc:client_id"] = forms.CharField(
            label="OIDC Client ID",
            required=True,
        )

        self.fields["oidc:client_secret"] = forms.CharField(
            label="OIDC Client Secret",
            required=True,
        )

class SettingsView(EventSettingsViewMixin, FormView):
    model = Event
    form_class = FsrWalletSettingsForm
    template_name = "pretix_fsr_wallet/settings.html"
    permission = "can_change_event_settings"

    def get_success_url(self) -> str:
        return reverse(
            "plugins:pretix_fsr_wallet:settings",
            kwargs={
                "organizer": self.request.event.organizer.slug,
                "event": self.request.event.slug,
            },
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obj"] = self.request.event
        kwargs["initial"] = self.request.event.settings.fsr_wallet_config
        return kwargs

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            if form.has_changed():
                self.request.event.settings.fsr_wallet_config = json.dumps(
                    form.cleaned_data, cls=I18nJSONEncoder
                )
                self.request.event.log_action(
                    "pretix.event.settings",
                    user=self.request.user,
                    data={"fsr_wallet_config": form.cleaned_data},
                )
            messages.success(self.request, _("Your changes have been saved."))
            return redirect(self.get_success_url())
        else:
            messages.error(
                self.request,
                _("We could not save your changes. See below for details."),
            )
            return self.render_to_response(self.get_context_data(form=form))