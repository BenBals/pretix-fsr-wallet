from typing import Union

import json
import logging
import requests
import urllib
from collections import OrderedDict
from decimal import Decimal
from django import forms
from django.http import HttpRequest
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from http.client import CREATED, OK
from jose import jws
from jsonschema.exceptions import ValidationError
from pretix.base.models import Order, OrderPayment, OrderRefund
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.multidomain.urlreverse import mainreverse
from secrets import token_hex
import datetime

import pretix_fsr_wallet.signals as signals

logger = logging.getLogger(__name__)


class Wallet(BasePaymentProvider):
    identifier = "wallet"
    verbose_name = _("VerDE Wallet")
    abort_pending_allowed = False

    oidc_public_key_cache = None
    oidc_public_key_cache_datetime = None

    @property
    def settings_form_fields(self):
        # TODO deal with trailing slashes
        d = OrderedDict(
            [
                (
                    "wallet_backend:url",
                    forms.URLField(
                        label="Wallet Backend URL",
                        initial=signals.default_config["wallet_backend:url"],
                        required=True,
                    ),
                ),
                (
                    "wallet_backend:api_key",
                    forms.CharField(
                        label="Wallet Backend API Key",
                        required=True,
                    ),
                ),
                (
                    "oidc:url",
                    forms.URLField(
                        label="OIDC Provider URL",
                        initial=signals.default_config["oidc:url"],
                        required=True,
                    ),
                ),
                (
                    "oidc:client_id",
                    forms.CharField(
                        label="OIDC Client ID",
                        required=True,
                    ),
                ),
                (
                    "oidc:client_secret",
                    forms.CharField(
                        label="OIDC Client Secret",
                        required=True,
                    ),
                ),
            ]
            + list(super().settings_form_fields.items())
        )
        d.move_to_end("_enabled", False)
        return d

    def settings_content_render(self, request: HttpRequest) -> str:
        template = get_template("pretix_fsr_wallet/settings_additional_info.html")
        ctx = {
            "request": request,
            "event": self.event,
            "redirect_url": self.redirect_url(request),
        }

        return template.render(ctx)

    def settings_form_clean(self, cleaned_data):
        # Reset oidc key cache, because the host could be changed
        self.oidc_public_key_cache = None
        self.oidc_public_key_cache_datetime = None

        return cleaned_data

    def payment_form_render(self, request) -> str:
        template = get_template("pretix_fsr_wallet/checkout_payment_form.html")
        ctx = {"request": request, "event": self.event, "settings": self.settings}
        return template.render(ctx)

    def checkout_confirm_render(self, request) -> str:
        template = get_template("pretix_fsr_wallet/checkout_payment_confirm.html")
        ctx = {"request": request, "event": self.event, "settings": self.settings}
        return template.render(ctx)

    def redirect_url(self, request):
        reversedurl = mainreverse("plugins:pretix_fsr_wallet:oidc_login_return")
        return request.build_absolute_uri(reversedurl)

    def checkout_prepare(self, request, total):
        state = token_hex(20)
        request.session["payment_wallet_oidc_state"] = state
        request.session["payment_wallet_event_pk"] = self.event.pk
        request.session["payment_wallet_organizer_pk"] = self.event.organizer.pk

        return (
            self.settings.get("oidc:url")
            + "/auth"
            + "?response_type=code&client_id="
            + self.settings.get("oidc:client_id")
            + "&redirect_uri="
            + urllib.parse.quote(self.redirect_url(request), safe="")
            + "&scope=openid&state="
            + state
        )

    def fetch_oidc_key_from_server(self):
        logger.info(f"Fetching new oidc public key from server {self.settings['oidc:url']}")

        get_resp = requests.get(f"{self.settings['oidc:url']}/certs")

        if get_resp.status_code != OK:
            logger.exception("Could not fetch OIDC public key, got response code ", get_resp.status_code)

        rsa_key = None
        for key in get_resp.json()["keys"]:
            if key["kid"] == "sig-rs-0":
                rsa_key = key

        if rsa_key is None:
            logger.exception("Could not fetch OIDC public key, got certs ", get_resp.json())
        else:
            self.oidc_public_key_cache_datetime = datetime.datetime.now()
            self.oidc_public_key_cache = rsa_key

    def get_oidc_public_key(self):
        print("Getting oidc public key")
        if self.oidc_public_key_cache is None or self.oidc_public_key_cache_datetime is None:
            self.fetch_oidc_key_from_server()
        else:
            key_age = datetime.datetime.now() - self.oidc_public_key_cache_datetime
            if key_age.total_seconds() > 86400:  # key is older than one day
                self.fetch_oidc_key_from_server()

        return self.oidc_public_key_cache

    def payment_is_valid_session(self, request):
        result = False

        if "payment_wallet_username" in request.session:
            return True

        try:
            code = request.session["payment_wallet_code"]

            token_response = requests.post(
                f"{self.settings.get('oidc:url')}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_url(request),
                    "client_id": self.settings.get("oidc:client_id"),
                    "client_secret": self.settings.get("oidc:client_secret"),
                },
            )

            if token_response.status_code != OK:
                print("Token response status code is ", token_response.status_code)
                return False

            data = token_response.json()
            print(data)

            print("OIDC public key", self.get_oidc_public_key())

            auth_info = jws.verify(
                data["id_token"], self.get_oidc_public_key(), algorithms=["RS256"]
            )
            request.session["payment_wallet_username"] = json.loads(auth_info)["sub"]
            result = True
        except TypeError:
            logger.exception("Could not verify oidc token!", request)
            return False

        return result

    def execute_payment_needs_user(self) -> bool:
        # The request session stores the user, thus the payment can only be made if that is present
        return True

    def wallet_backend_authorization_header(self):
        return {"Authorization": f"Bearer {self.settings['wallet_backend:api_key']}"}

    def set_info_key_on_payment_or_refund(
        self, obj: OrderPayment | OrderRefund, key: str, value
    ):
        current = obj.info_data
        current[key] = value
        obj.info_data = current
        print("Set info on payment/refund, now it's", obj.info_data)

    def _transaction(self, user, decimal_amount, full_id, type):
        amount = int(decimal_amount * 100)
        request_body = {
            "amount": amount,
            "description": f"{type} {full_id} at {self.event.name}",
            "tag": "event",
            "idempotency_key": full_id,
        }

        return requests.post(
            f"{self.settings['wallet_backend:url']}/pos/wallets/user/{user}/transactions",
            json=request_body,
            headers=self.wallet_backend_authorization_header(),
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        print("Trying to execute payment")
        try:
            user = request.session["payment_wallet_username"]
        except KeyError:
            self.set_info_key_on_payment_or_refund(
                payment, "last_error", "User session not authenticated against OIDC."
            )
            raise PaymentException(
                _(
                    "We could not authenticate you. Please retry the payment. Contact us if the problem persists."
                )
            )

        print("Checking balance", user)
        get_resp = requests.get(
            f"{self.settings['wallet_backend:url']}/pos/wallets/user/{user}",
            headers=self.wallet_backend_authorization_header(),
        )

        print(get_resp.json())

        if get_resp.status_code != OK:
            raise PaymentException(
                _(
                    "We could not fetch your balance from VerDE Wallet. You can check your balance at wallet.myphi.de. "
                    "If you have already paid in money, please allow some time for us to manually "
                    "process it. If you have not paid in money, see myhpi.de/wallet for how to do "
                    "that. Your order has been created and your tickets are reserved until the "
                    "payment deadline shown below. Note that you will have to manually retry the payment after your "
                    "deposit has been credited."
                )
            )

        balance = get_resp.json()["data"]["balance"]  # cents
        amount = int(payment.amount * 100)  # cents
        print("Checked balance", balance, amount)

        if balance < amount:
            raise PaymentException(
                _(
                    "Your balance is not sufficient. You can check your balance at wallet.myphi.de. "
                    "If you have already paid in money, please allow some time for us to manually "
                    "process it. If you have not paid in money, see myhpi.de/wallet for how to do "
                    "that. Your order has been created and your tickets are reserved until the "
                    "payment deadline shown below. Note that you will have to manually retry the "
                    "payment after your deposit has been credited."
                )
            )

        post_resp = self._transaction(
            user, -1 * payment.amount, payment.full_id, "Payment"
        )
        print(post_resp.status_code)

        if post_resp.status_code == CREATED:
            print("Payment successfull")
            self.set_info_key_on_payment_or_refund(
                payment, "success", post_resp.json()["data"]
            )
            self.set_info_key_on_payment_or_refund(payment, "username", user)
            self.set_info_key_on_payment_or_refund(payment, "last_error", None)
            payment.confirm()
        else:
            self.set_info_key_on_payment_or_refund(
                payment, "last_error", post_resp.json()
            )
            raise PaymentException(
                _(
                    "Unfortunately, we could not process your transaction. Please try again or "
                    "contact us."
                )
            )
        return None

    def execute_refund(self, refund: OrderRefund):
        try:
            user = (
                refund.info_data["username"]
                if refund.info_data
                else refund.payment.info_data["username"]
            )
            post_resp = self._transaction(user, refund.amount, refund.full_id, "Refund")

            self.set_info_key_on_payment_or_refund(refund, "username", user)

            if post_resp.status_code == CREATED:
                self.set_info_key_on_payment_or_refund(
                    refund, "success", post_resp.json()["data"]
                )
                self.set_info_key_on_payment_or_refund(refund, "last_error", None)
                refund.done()
            else:
                logger.exception("VerDE Wallet error: %s" % str(post_resp.json()))
                self.set_info_key_on_payment_or_refund(
                    refund, "last_error", post_resp.json()
                )
                raise PaymentException(
                    _(
                        "Could not refund to VerDE Wallet. Please try again and contact us if the "
                        "problem persists."
                    )
                )
        except requests.exceptions.RequestException as e:
            logger.exception("VerDE Wallet error: %s" % str(e))
            self.set_info_key_on_payment_or_refund(refund, "last_error", str(e))
            raise PaymentException(
                _(
                    "We had trouble communicating with VerDE Wallet. Please try again and contact "
                    "us if the problem persists."
                )
            )
        except KeyError as e:
            logger.exception("VerDE Wallet kef e: %s" % str(e))
            self.set_info_key_on_payment_or_refund(
                refund, "last_error", "Could not find user associated with payment."
            )
            raise PaymentException(
                _(
                    "We could not find the VerDE Wallet account associated with the original "
                    "payment. Please try again and contact us if the problem persists."
                )
            )

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        retry = True
        try:
            if payment.info_data.get("paymentState") == "PENDING":
                retry = False
        except KeyError:
            pass
        template = get_template("pretix_fsr_wallet/pending.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "retry": retry,
            "order": payment.order,
        }
        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_fsr_wallet/control_payment.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "payment_info": payment.info_data,
            "order": payment.order,
            "provname": self.verbose_name,
        }
        return template.render(ctx)

    def refund_control_render(self, request: HttpRequest, refund: OrderRefund):
        template = get_template("pretix_fsr_wallet/control_refund.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "refund_info": refund.info_data,
            "order": refund.order,
            "provname": self.verbose_name,
        }
        return template.render(ctx)

    class NewRefundForm(forms.Form):
        username = forms.CharField(
            label=_("OIDC Username"),
            required=False,
        )

    def new_refund_control_form_render(self, request: HttpRequest, order: Order):
        form = self.NewRefundForm(
            prefix="refund-wallet",
            data=request.POST
            if request.method == "POST"
            else None,
        )
        template = get_template("pretix_fsr_wallet/new_refund_control_form.html")
        ctx = {
            "form": form,
        }
        return template.render(ctx)

    def new_refund_control_form_process(
        self, request: HttpRequest, amount: Decimal, order: Order
    ) -> OrderRefund:
        f = self.NewRefundForm(prefix="refund-wallet", data=request.POST)

        if not f.is_valid():
            raise ValidationError(
                _("Your input was invalid, please see below for details.")
            )

        print(request.POST)
        if request.POST.get("refund-wallet-username") == '' and float(request.POST.get("newrefund-wallet")) > 0:
            print("Raising error")
            raise ValidationError(
                "If you want to issue a refund via VerDE Wallet, please provide the OIDC username the refund should "
                "be issued to"
            )
        print("Passed test")

        d = {"username": f.cleaned_data["username"], "type": "manual"}
        return OrderRefund(
            order=order,
            payment=None,
            state=OrderRefund.REFUND_STATE_CREATED,
            amount=amount,
            provider=self.identifier,
            info=json.dumps(d),
        )

    def order_can_retry(self, order):
        return True

    def payment_refund_supported(self, payment: OrderPayment):
        return True

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return True

    def shred_payment_info(self, obj: Union[OrderPayment, OrderRefund]):
        d = obj.info_data
        new = {"_shreded": True}
        for k in "success":
            if k in d:
                new[k] = d[k]
        obj.info_data = new
        obj.save(update_fields=["info"])
        for le in (
            obj.order.all_logentries()
            .filter(action_type="pretix_sofort.sofort.event")
            .exclude(data="")
        ):
            d = le.parsed_data
            new = {"_shreded": True}
            for k in "success":
                if k in d:
                    new[k] = d[k]
            le.data = json.dumps(new)
            le.shredded = True
            le.save(update_fields=["data", "shredded"])
