import json
import requests

from flask import Blueprint, current_app, jsonify, request
from .utils import (
    build_endpoint,
    format_request_and_response,
)
from .identity import build_headers
from .orders import default_shipping_address

bp = Blueprint("vault", __name__, url_prefix="/vault")


class Vault:
    def __init__(self, **kwargs):
        self.auth_header = kwargs.get("auth-header")
        self._set_partner_config(kwargs)
        self._set_billing_address(kwargs)
        self.payment_source_type = kwargs.get(
            "payment-source",
            "card",  # If 'payment-source' is undefined, it must be a card transaction!
        )

        self.vault_level = kwargs.get("vault-level")
        self.vault_id = kwargs.get("vault-id")
        self.customer_id = kwargs.get("customer-id") or "NtiESbVfPx"
        print(f"Customer ID: {self.customer_id}")

        self.permit_multiple_payment_tokens = bool(
            kwargs.get("permit-multiple-payment-tokens")
        )

        self.shipping_preference = kwargs.get("shipping-preference", "NO_SHIPPING")
        self.include_shipping_address = kwargs.get("include-shipping-address", False)

        try:
            self.include_auth_assertion = bool(kwargs["include-auth-assertion"])
        except KeyError:
            self.include_auth_assertion = self.vault_level == "MERCHANT"
        self.include_request_id = (
            True  # This is required to specify `experience_context`.
        )
        if "setup-token-id" in kwargs:
            self.setup_token = kwargs["setup-token-id"]
        if "payment-token-id" in kwargs:
            self.payment_token = kwargs["payment-token-id"]
        self.three_d_secure_preference = kwargs.get("3ds-preference")

        self.formatted = dict()

    def _set_partner_config(self, kwargs):
        self.partner_id = kwargs.get("partner-id")
        self.client_id = kwargs.get("partner-client-id")
        self.secret = kwargs.get("partner-secret")
        self.bn_code = kwargs.get("partner-bn-code")
        self.merchant_id = kwargs.get("merchant-id")

        if self.client_id == current_app.config["PARTNER_CLIENT_ID"]:
            self.secret = current_app.config["PARTNER_SECRET"]

    def _set_billing_address(self, kwargs):
        self.cardholder_name = kwargs.get("cardholder-name")
        self.billing_address = {
            "address_line_1": kwargs.get("billing-address-line-1"),
            "address_line_2": kwargs.get("billing-address-line-2"),
            "admin_area_1": kwargs.get("billing-address-admin-area-1"),
            "admin_area_2": kwargs.get("billing-address-admin-area-2"),
            "postal_code": kwargs.get("billing-address-postal-code"),
            "country_code": kwargs.get("billing-address-country-code", "").upper(),
        }

        for key, val in dict(self.billing_address).items():
            if not val:
                del self.billing_address[key]

    def build_headers(self):
        """Wrapper for .utils.build_headers."""
        if self.include_auth_assertion:
            merchant_id = self.merchant_id
        else:
            merchant_id = None

        headers = build_headers(
            client_id=self.client_id,
            secret=self.secret,
            bn_code=self.bn_code,
            auth_header=self.auth_header,
            merchant_id=merchant_id,
            include_request_id=self.include_request_id,
        )
        self.formatted |= headers.pop("formatted")

        self.auth_header = headers["Authorization"]
        return headers

    def build_payment_source(self, for_token):
        """Return the payment source object appropriate for the type of token being created."""
        match for_token:
            case "setup":
                experience_context = {
                    "return_url": "https://go/alice/returnUrl",
                    "cancel_url": "https://go/alice/cancelUrl",
                }
                if self.shipping_preference:
                    experience_context["shipping_preference"] = self.shipping_preference

                payment_source_body = {
                    "permit_multiple_payment_tokens": self.permit_multiple_payment_tokens,
                    "usage_type": self.vault_level,
                    "experience_context": experience_context,
                }
                if self.include_shipping_address:
                    payment_source_body["shipping"] = default_shipping_address()

                match self.payment_source_type:
                    case "paypal":
                        description = "A PayPal payment source."
                    case "venmo":
                        description = "A Venmo payment source."
                    case "card":
                        description = "A card payment source."
                        if self.three_d_secure_preference:
                            payment_source_body["verification_method"] = (
                                self.three_d_secure_preference
                            )
                        if self.billing_address:
                            payment_source_body["billing_address"] = (
                                self.billing_address
                            )
                        if self.cardholder_name:
                            payment_source_body["name"] = self.cardholder_name

                    case _:
                        description = (
                            f"A {self.payment_source_type.title()} payment source."
                        )

                payment_source_body["description"] = description
                payment_source = {self.payment_source_type: payment_source_body}

            case "payment":
                payment_source = {
                    "token": {
                        "id": self.setup_token,
                        "type": "SETUP_TOKEN",
                    }
                }
            case _:
                raise ValueError(f"{for_token=}")
        return payment_source

    def create_setup_token(self):
        """Create a setup token with the POST /v3/vault/setup-tokens endpoint.

        Docs: https://developer.paypal.com/docs/api/payment-tokens/v3/#setup-tokens_create
        """
        endpoint = build_endpoint("/v3/vault/setup-tokens")
        try:
            headers = self.build_headers()
        except KeyError:
            return {"formatted": self.formatted}

        data = {
            "payment_source": self.build_payment_source(for_token="setup"),
        }

        if self.customer_id:
            data["customer"] = {"id": self.customer_id}

        response = requests.post(
            endpoint,
            headers=headers,
            json=data,
        )
        self.formatted["create-setup-token"] = format_request_and_response(response)
        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }

        try:
            setup_token_id = response.json()["id"]
        except Exception as exc:
            current_app.logger.error(
                f"Encountered exception unpacking setup token: {exc}"
            )
        else:
            return_val["setupTokenId"] = setup_token_id
        finally:
            return return_val

    def create_payment_token(self):
        """Create a payment token using the POST /v3/vault/payment-tokens endpoint.

        Docs: https://developer.paypal.com/docs/api/payment-tokens/v3/#payment-tokens_create
        """
        endpoint = build_endpoint("/v3/vault/payment-tokens")
        try:
            headers = self.build_headers()
        except KeyError:
            return {"formatted": self.formatted}

        data = {
            "payment_source": self.build_payment_source(for_token="payment"),
        }

        response = requests.post(
            endpoint,
            headers=headers,
            json=data,
        )
        self.formatted["create-payment-token"] = format_request_and_response(response)
        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }

        try:
            payment_token_id = response.json()["id"]
        except Exception as exc:
            current_app.logger.error(
                f"Encountered exception unpacking setup token: {exc}"
            )
        else:
            return_val["paymentTokenId"] = payment_token_id
        finally:
            return return_val

    def delete_payment_token(self):
        """Delete the payment token using the DELETE /v3/vault/payment-tokens/{payment_token_id} endpoint.

        Docs: https://developer.paypal.com/docs/api/payment-tokens/v3/#payment-tokens_delete
        """
        endpoint = build_endpoint(f"/v3/vault/payment-tokens/{self.payment_token}")
        try:
            headers = self.build_headers()
        except KeyError:
            return {"formatted": self.formatted}

        response = requests.delete(endpoint, headers=headers)
        self.formatted["delete-payment-token"] = format_request_and_response(response)
        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }

        return return_val

    def get_payment_token_status(self):
        """Retrieve the payment token status using the GET /v3/vault/payment-tokens/{payment_token_id} endpoint.

        Docs: https://developer.paypal.com/docs/api/payment-tokens/v3/#payment-tokens_get
        """
        endpoint = build_endpoint(f"/v3/vault/payment-tokens/{self.payment_token}")
        try:
            headers = self.build_headers()
        except KeyError:
            return {"formatted": self.formatted}

        response = requests.get(endpoint, headers=headers)
        self.formatted["payment-token-status"] = format_request_and_response(response)
        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }

        return return_val

    def get_payment_tokens(self):
        """Retrieve all payment tokens for a customer using the GET /v3/vault/payment-tokens endpoint.

        Docs: https://developer.paypal.com/docs/api/payment-tokens/v3/#customer_payment-tokens_get
        """
        endpoint = build_endpoint(
            f"/v3/vault/payment-tokens", query={"customer_id": self.customer_id}
        )
        try:
            headers = self.build_headers()
        except KeyError:
            return {"formatted": self.formatted}

        response = requests.get(endpoint, headers=headers)
        self.formatted["get-payment-tokens"] = format_request_and_response(response)
        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }

        return return_val

    # def get_payment_tokens_by_merchant_customer_id(self):
    #     """Retrieve all payment tokens for a customer using the GET /v3/vault/payment-tokens endpoint.

    #     Docs: https://developer.paypal.com/docs/api/payment-tokens/v3/#customer_payment-tokens_get
    #     """
    #     endpoint = build_endpoint(
    #         f"/v3/vault/payment-tokens",
    #         query={"merchant_customer_id": self.merchant_customer_id},
    #     )
    #     try:
    #         headers = self.build_headers()
    #     except KeyError:
    #         return {"formatted": self.formatted}

    #     response = requests.get(endpoint, headers=headers)
    #     self.formatted["get-payment-tokens-by-mcid"] = format_request_and_response(
    #         response
    #     )
    #     return_val = {
    #         "formatted": self.formatted,
    #         "authHeader": self.auth_header,
    #     }

    #     return return_val


@bp.route("/setup-tokens", methods=("POST",))
def create_setup_token():
    """Create a Vault v3 setup token.

    Wrapper for Vault.create_setup_token.
    """
    data = request.get_json()

    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Creating a vault setup token with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    vault = Vault(**data)
    resp = vault.create_setup_token()

    return jsonify(resp)


@bp.route("/setup-tokens/<setup_token_id>", methods=("POST",))
def create_payment_token(setup_token_id):
    """Create a Vault v3 payment token using the given setup token ID.

    Wrapper for Vault.create_payment_token.
    """
    data = request.get_json()
    data["setup-token-id"] = setup_token_id

    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Creating a vault payment token with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    vault = Vault(**data)
    resp = vault.create_payment_token()

    return jsonify(resp)


@bp.route("/payment-tokens/<payment_token_id>", methods=("POST",))
def get_payment_token_status(payment_token_id):
    """Retrieve the status of the payment token with the given ID.

    Wrapper for Vault.get_payment_token_status.
    """
    data = request.get_json()
    data["payment-token-id"] = payment_token_id

    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Getting the status of payment token with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    vault = Vault(**data)
    resp = vault.get_payment_token_status()

    return jsonify(resp)


@bp.route("/payment-tokens/<payment_token_id>", methods=("DELETE",))
def delete_payment_token(payment_token_id):
    """Delete the payment token with the given ID.

    Wrapper for Vault.delete_payment_token.
    """

    data = request.get_json()
    data["payment-token-id"] = payment_token_id
    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Deleting payment token with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    vault = Vault(**data)
    resp = vault.delete_payment_token()

    return jsonify(resp)


@bp.route("/customers/<customer_id>", methods=("POST",))
def get_payment_tokens(customer_id):
    """Retrieve all payment tokens for the customer with the given ID.

    Wrapper for Vault.get_payment_tokens.
    """

    data = request.get_json()
    data["customer-id"] = customer_id
    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Getting the payment tokens of a customer with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    vault = Vault(**data)
    resp = vault.get_payment_tokens()

    return jsonify(resp)


# @bp.route("/merchant-customers/<merchant_customer_id>", methods=("POST",))
# def get_payment_tokens_by_merchant_customer_id(merchant_customer_id):
#     """Retrieve all payment tokens for the customer with the given ID.

#     Wrapper for Vault.get_payment_tokens.
#     """

#     data = request.get_json()
#     data["merchant-customer-id"] = merchant_customer_id
#     data_filtered = {key: value for key, value in data.items() if value}
#     current_app.logger.info(
#         f"Getting the payment tokens of a customer with (filtered) data = {json.dumps(data_filtered, indent=2)}"
#     )

#     vault = Vault(**data)
#     resp = vault.get_payment_tokens_by_merchant_customer_id()

#     return jsonify(resp)
