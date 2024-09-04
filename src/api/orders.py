import json
import requests

from flask import Blueprint, request, current_app, jsonify

from .identity import build_headers
from .utils import build_endpoint, format_request_and_response


bp = Blueprint("orders", __name__, url_prefix="/orders")


def default_shipping_address():
    return {
        "name": {"full_name": "Myfuhl Name"},
        "address": {
            "address_line_1": "1324 Permutation Pattern Parkway",
            "admin_area_2": "Gainesville",
            "admin_area_1": "FL",
            "postal_code": "32601",
            "country_code": "US",
        },
    }


class Order:
    def __init__(self, **kwargs):
        self._set_partner_config(kwargs)
        self.order_id = kwargs.get("order-id") or None  # Coerce to None if empty
        self.auth_id = kwargs.get("auth-id")

        self.auth_header = kwargs.get("auth-header")
        self.payment_source_type = kwargs.get("payment-source", None)
        self.single_use_token = kwargs.get("single-use-token", None)

        self.currency_code = kwargs.get("currency-code", "USD")
        self.intent = kwargs.get("intent")
        self.user_action = kwargs.get("user-action")
        self.disbursement_mode = kwargs.get("disbursement-mode")

        self.reference_id = kwargs.get("reference-id")
        self.custom_id = kwargs.get("custom-id")
        self.soft_descriptor = kwargs.get("soft-descriptor")
        self.shipping_preference = kwargs.get("shipping-preference")

        self.vault_flow = kwargs.get("vault-flow")
        self.vault_level = kwargs.get("vault-level")
        self.vault_id = kwargs.get("vault-id")
        self.customer_id = kwargs.get("customer-id")
        self.merchant_customer_id = kwargs.get("merchant-customer-id")
        self.permit_multiple_payment_tokens = bool(
            kwargs.get("permit-multiple-payment-tokens", "true")
        )

        try:
            if self.merchant_id == self.partner_id:
                self.include_auth_assertion = False
            else:
                self.include_auth_assertion = bool(kwargs["include-auth-assertion"])
        except KeyError:
            self.include_auth_assertion = (self.vault_level == "MERCHANT") or (
                self.single_use_token is not None
            )

        self.include_payee = not self.include_auth_assertion
        self.include_request_id = (
            True  # This is required to specify `experience_context`.
        )

        self.mock_header = kwargs.get("mock-header") or None

        self.ba_id = kwargs.get("ba-id")

        self.include_shipping_options = kwargs.get("include-shipping-options")
        self.shipping_cost = 9.99
        self.include_shipping_address = kwargs.get("include-shipping-address")

        self.partner_fee = float(kwargs.get("partner-fee", "0"))
        self.item_price = kwargs.get("item-price")
        self.item_tax = float(kwargs.get("item-tax", "0"))
        self.item_category = kwargs.get("item-category")

        self.include_custom_purchase_unit_field = kwargs.get(
            "include-custom-purchase-unit-field"
        )
        self.custom_purchase_unit_key = kwargs.get("custom-purchase-unit-key")
        self.custom_purchase_unit_value = kwargs.get("custom-purchase-unit-value")

        self.three_d_secure_preference = kwargs.get("3ds-preference")

        self.formatted = dict()
        self.breakdown = dict()

    def _set_partner_config(self, kwargs):
        self.partner_id = kwargs.get("partner-id")
        self.client_id = kwargs.get("partner-client-id")
        self.secret = kwargs.get("partner-secret")
        self.bn_code = kwargs.get("partner-bn-code")
        self.merchant_id = kwargs.get("merchant-id")

        if self.client_id == current_app.config["PARTNER_CLIENT_ID"]:
            self.secret = current_app.config["PARTNER_SECRET"]
        if self.client_id == current_app.config["FASTLANE_PARTNER_CLIENT_ID"]:
            self.secret = current_app.config["FASTLANE_PARTNER_SECRET"]
        if self.client_id == current_app.config["FASTLANE_MERCHANT_CLIENT_ID"]:
            self.secret = current_app.config["FASTLANE_MERCHANT_SECRET"]

    def to_amount_dict(self, amount):
        if isinstance(amount, str):
            amount = float(amount)
        return {
            "currency_code": self.currency_code,
            "value": amount,
        }

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

    def build_platform_fees(self):
        """Return the platform fee object for the order.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#definition-platform_fee
        """
        platform_fees = []
        if self.partner_fee > 0:
            platform_fees.append(
                {
                    "amount": self.to_amount_dict(self.partner_fee),
                    "payee": {
                        "merchant_id": self.partner_id,
                    },
                }
            )
        return platform_fees

    def build_payment_instruction(self, for_call):
        """Return the payment instruction object for the order.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#definition-payment_instruction
        """
        payment_instruction = dict()

        match (self.intent, for_call):
            case ("CAPTURE", "create") | ("AUTHORIZE", "capture"):
                if self.disbursement_mode == "DELAYED":
                    payment_instruction["disbursement_mode"] = self.disbursement_mode

                platform_fees = self.build_platform_fees()
                if platform_fees:
                    payment_instruction["platform_fees"] = platform_fees

        return payment_instruction

    def build_shipping_option(self):
        """Return a default shipping option object."""
        return {
            "id": "shipping-default",
            "label": "A default shipping option",
            "selected": True,
            "amount": self.to_amount_dict(self.shipping_cost),
        }

    def build_shipping(self):
        """Return the shipping object for the order.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#definition-shipping_detail
        """
        shipping = dict()

        if self.include_shipping_address:
            shipping |= default_shipping_address()
            if not self.include_shipping_options:
                shipping["type"] = "SHIPPING"

        if self.include_shipping_options:
            shipping_options = [self.build_shipping_option()]
            shipping["options"] = shipping_options
            self.breakdown["shipping"] = self.to_amount_dict(self.shipping_cost)

        return shipping

    def build_line_item(self):
        """Return the line item object for the order.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#definition-item
        """
        match self.item_category:
            case "PHYSICAL_GOODS":
                name = "A physical good."
            case "DIGITAL_GOODS":
                name = "A digital good."
            case "DONATION":
                name = "A donation."
            case None | "None":
                name = "A good of unspecified category."
                self.item_category = None
            case _:
                raise ValueError

        unit_amount = self.to_amount_dict(self.item_price)
        item = {
            "name": name,
            "quantity": 1,
            "unit_amount": unit_amount,
        }
        self.breakdown["item_total"] = unit_amount

        if self.item_category is not None:
            item["category"] = self.item_category

        if self.item_tax:
            tax_amount = self.to_amount_dict(self.item_tax)
            item["tax"] = tax_amount
            self.breakdown["tax_total"] = tax_amount

        return item

    def build_purchase_unit(self):
        """Return the purchase unit object for the order.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#definition-purchase_unit
        """
        purchase_unit = dict()
        if self.include_payee:
            purchase_unit["payee"] = {"merchant_id": self.merchant_id}

        if self.reference_id:
            purchase_unit["reference_id"] = self.reference_id
        if self.custom_id:
            purchase_unit["custom_id"] = self.custom_id
        if self.soft_descriptor:
            purchase_unit["soft_descriptor"] = self.soft_descriptor

        if self.include_custom_purchase_unit_field:
            value = self.custom_purchase_unit_value
            try:
                value = json.loads(value)
            except json.decoder.JSONDecodeError:
                current_app.logger.info(
                    f"\n\nError JSON-parsing value:\n{repr(value)}\n\n"
                )
                # `value` may contain "\n" and "\r" characters that impede loading,
                # so we replace them with whitespace.
                value = value.replace("\\n", " ").replace("\\r", " ")
                current_app.logger.info(
                    f"\tTrying again with value:\n{repr(value)}\n\n"
                )
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError as exc:
                    current_app.logger.error(
                        f"\t\tUtterly failed to json.loads {repr(self.custom_purchase_unit_value)=}"
                    )
            finally:
                purchase_unit[self.custom_purchase_unit_key] = value

        payment_instruction = self.build_payment_instruction(for_call="create")
        if payment_instruction:
            purchase_unit["payment_instruction"] = payment_instruction

        shipping = self.build_shipping()
        if shipping:
            purchase_unit["shipping"] = shipping

        purchase_unit["items"] = [self.build_line_item()]
        total_price = round(
            sum(float(cost["value"]) for cost in self.breakdown.values()), 2
        )
        amount = self.to_amount_dict(total_price) | {"breakdown": self.breakdown}
        purchase_unit["amount"] = amount
        return purchase_unit

    def build_context(self):
        """Return the experience/application context object for the order.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#definition-experience_context_base
        Docs: https://developer.paypal.com/docs/api/orders/v2/#definition-order_application_context
        """
        context = {}

        if self.shipping_preference:
            context["shipping_preference"] = self.shipping_preference

        if self.payment_source_type == "card":
            return context

        context |= {
            "return_url": "https://go/alice/return",
            "cancel_url": "https://go/alice/cancel",
        }
        if self.user_action:
            context["user_action"] = self.user_action

        return context

    def build_payment_source_for_authorize(self):
        """Return the payment source object appropriate for the type of call being made."""
        payment_source = {}

        if self.payment_source_type == "card" and self.three_d_secure_preference:
            return {
                "card": {
                    "attributes": {
                        "verification": {
                            "method": self.three_d_secure_preference,
                        }
                    }
                }
            }

        if self.ba_id:
            return {
                "token": {
                    "id": self.ba_id,
                    "type": "BILLING_AGREEMENT",
                }
            }
        elif self.vault_flow == "buyer-not-present" and self.vault_id:
            return {
                "vault_id": self.vault_id,
            }

        return payment_source

    def build_payment_source_for_create(self):
        """Return the payment source object appropriate fora the type of call being made."""

        if self.ba_id and self.intent == "AUTHORIZE":
            payment_source = {
                "token": {
                    "id": self.ba_id,
                    "type": "BILLING_AGREEMENT",
                },
            }
            return payment_source

        if self.single_use_token:
            payment_source = {
                "card": {
                    "single_use_token": self.single_use_token,
                },
            }
            return payment_source

        payment_source_body = {}
        attributes = {}

        if self.payment_source_type == "card":
            if self.three_d_secure_preference:
                attributes["verification"] = {
                    "method": self.three_d_secure_preference,
                }

        context = self.build_context()
        if context:
            payment_source_body["experience_context"] = context

        customer = {}
        match self.vault_flow:
            case "buyer-not-present":
                if not self.vault_id:
                    return {}

                del payment_source_body["experience_context"]
                payment_source_body["vault_id"] = self.vault_id

            case "first-time-buyer":
                attributes["vault"] = {
                    "store_in_vault": "ON_SUCCESS",
                    "usage_type": self.vault_level,
                    "permit_multiple_payment_tokens": self.permit_multiple_payment_tokens,
                }
                if self.customer_id:
                    customer["id"] = self.customer_id
                if self.merchant_customer_id:
                    customer["merchant_customer_id"] = self.merchant_customer_id

            case "return-buyer":
                if self.customer_id:
                    customer["id"] = self.customer_id
        if customer:
            attributes["customer"] = customer
        if attributes:
            payment_source_body["attributes"] = attributes

        if payment_source_body:
            return {self.payment_source_type: payment_source_body}
        else:
            return {}

    def create(self):
        """Create the order with the POST /v2/checkout/orders endpoint.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#orders_create
        """
        endpoint = build_endpoint("/v2/checkout/orders")
        try:
            headers = self.build_headers()
        except KeyError as exc:
            current_app.logger.error(
                f"Encountered KeyError in Orders().build_headers: {exc}"
            )
            return {"formatted": self.formatted}
        else:
            if self.mock_header:
                if (
                    self.mock_header.startswith("capture")
                    and self.vault_flow == "buyer-not-present"
                    and self.vault_id
                ):
                    mock_header = self.mock_header.removeprefix("capture-")
                    headers["PayPal-Mock-Response"] = json.dumps(
                        {"mock_application_codes": mock_header}
                    )
                elif self.mock_header.startswith("create"):
                    mock_header = self.mock_header.removeprefix("create-")
                    headers["PayPal-Mock-Response"] = json.dumps(
                        {"mock_application_codes": mock_header}
                    )

        purchase_units = [self.build_purchase_unit()]
        data = {
            "intent": self.intent,
            "purchase_units": purchase_units,
        }
        payment_source = self.build_payment_source_for_create()
        if payment_source:
            data["payment_source"] = payment_source

        response = requests.post(
            endpoint,
            headers=headers,
            json=data,
        )

        self.formatted["create-order"] = format_request_and_response(response)
        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }
        try:
            response_data = response.json()
        except:
            return return_val

        try:
            order_id = response_data["id"]
        except (KeyError, IndexError) as exc:
            current_app.logger.error(
                f"Encountered generic exception unpacking order ID: {exc}"
            )
        else:
            return_val["orderId"] = order_id

        try:
            authorization = response_data["purchase_units"][0]["payments"][
                "authorizations"
            ][0]
            auth_id = authorization["id"]
            auth_status = authorization["status"]
        except (KeyError, IndexError) as exc:
            current_app.logger.info(
                f"Unable to extract auth_id from {json.dumps(response_data, indent=2)}"
            )
        else:
            return_val["authId"] = auth_id
            return_val["authStatus"] = auth_status

        try:
            capture = response_data["purchase_units"][0]["payments"]["captures"][0]
            capture_id = capture["id"]
            capture_status = capture["status"]
        except (KeyError, IndexError) as exc:
            current_app.logger.info(
                f"Unable to extract capture_id from {json.dumps(response_data, indent=2)}"
            )
        else:
            return_val["captureId"] = capture_id
            return_val["captureStatus"] = capture_status

        return return_val

    def capture(self):
        """Capture the order using the the POST /v2/checkout/orders/{order_id}/capture endpoint.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#orders_capture
        """
        if not self.order_id:
            raise ValueError

        if self.intent == "AUTHORIZE":
            return self.auth_and_capture()

        endpoint = build_endpoint(f"/v2/checkout/orders/{self.order_id}/capture")
        try:
            headers = self.build_headers()
        except KeyError:
            return {"formatted": self.formatted}
        else:
            if self.mock_header and self.mock_header.startswith("capture"):
                mock_header = self.mock_header.removeprefix("capture-")
                headers["PayPal-Mock-Response"] = json.dumps(
                    {"mock_application_codes": mock_header}
                )

        data = {}
        payment_instruction = self.build_payment_instruction(for_call="capture")
        if payment_instruction:
            data["payment_instruction"] = payment_instruction

        response = requests.post(endpoint, headers=headers, json=data)
        self.formatted["capture-order"] = format_request_and_response(response)
        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }
        try:
            response_dict = response.json()
        except json.JSONDecodeError as exc:
            current_app.logger.error(
                f"Encountered {exc} while unpacking capture response:\n{response.text}"
            )
        else:
            try:
                capture_status = response_dict["purchase_units"][0]["payments"][
                    "captures"
                ][0]["status"]
            except (KeyError, IndexError) as exc:
                capture_status = None
            finally:
                return_val["captureStatus"] = capture_status
        finally:
            return return_val

    def _authorize(self):
        """Authorize the order using the POST /v2/checkout/orders/{order_id}/authorize endpoint.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#orders_authorize
        """
        endpoint = build_endpoint(f"/v2/checkout/orders/{self.order_id}/authorize")

        try:
            headers = self.build_headers()
        except KeyError:
            return
        else:
            if self.mock_header:
                if self.mock_header.startswith("authorize"):
                    mock_header = self.mock_header.removeprefix("authorize-")
                    headers["PayPal-Mock-Response"] = json.dumps(
                        {"mock_application_codes": mock_header}
                    )

        data = {}
        if self.reference_id:
            data["reference_id"] = self.reference_id
        payment_source = self.build_payment_source_for_authorize()
        if payment_source:
            data["payment_source"] = payment_source

        response = requests.post(endpoint, headers=headers, json=data)
        self.formatted["authorize-order"] = format_request_and_response(response)

        try:
            auth_id = response.json()["purchase_units"][0]["payments"][
                "authorizations"
            ][0]["id"]
        except (TypeError, IndexError, KeyError) as exc:
            current_app.logger.error(
                f"Error accessing authorization ID from response: {exc}"
            )
        else:
            self.auth_id = auth_id
        finally:
            return

    def _capture_authorization(self):
        """Capture the authorization using the POST /v2/payments/authorizations/{auth_id}/capture endpoint.

        Docs: https://developer.paypal.com/docs/api/payments/v2/#authorizations_capture
        """
        endpoint = build_endpoint(f"/v2/payments/authorizations/{self.auth_id}/capture")
        headers = self.build_headers()

        data = {}
        payment_instruction = self.build_payment_instruction(for_call="capture")
        if payment_instruction:
            data["payment_instruction"] = payment_instruction

        response = requests.post(endpoint, headers=headers, json=data)
        self.formatted["capture-authorization"] = format_request_and_response(response)

        try:
            response_dict = response.json()
        except json.JSONDecodeError as exc:
            current_app.logger.error(
                f"Encountered {exc} while unpacking capture response:\n{response.text}"
            )
            return

        try:
            capture_status = response_dict["purchase_units"][0]["payments"]["captures"][
                0
            ]["status"]
        except (KeyError, IndexError) as exc:
            return

        return capture_status

    def auth_and_capture(self):
        """Authorize the order and then capture the resulting authorization."""
        if self.auth_id is None:
            self._authorize()

        return_val = dict()
        if self.auth_id is not None:
            capture_status = self._capture_authorization()
            if capture_status is not None:
                return_val["captureStatus"] = capture_status

        return_val |= {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }
        return return_val

    def get_details(self):
        """Retrieve the order details using the GET /v2/checkout/orders/{order_id} endpoint.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#orders_get
        """
        if self.order_id is None:
            raise ValueError

        try:
            headers = self.build_headers()
        except KeyError as exc:
            current_app.logger.error(f"KeyError encountered building headers: {exc}")
            return {"formatted": self.formatted}

        endpoint = build_endpoint(f"/v2/checkout/orders/{self.order_id}")

        response = requests.get(endpoint, headers=headers)
        self.formatted["order-details"] = format_request_and_response(response)

        return_val = {
            "formatted": self.formatted,
            "authHeader": self.auth_header,
        }
        return return_val


@bp.route("/", methods=("POST",))
def create_order():
    """Create an order.

    Wrapper for Order.create.
    """
    data = request.get_json()
    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        "\n".join(
            [
                f"Creating an order with (filtered) data = ",
                json.dumps(data_filtered, indent=2, sort_keys=True),
            ]
        )
    )

    order = Order(**data)
    resp = order.create()

    return jsonify(resp)


@bp.route("/<order_id>/capture", methods=("POST",))
def capture_order(order_id):
    """Capture the order with the given ID.

    Wrapper for Order.capture.
    """
    data = request.get_json()
    data["order-id"] = order_id
    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Capturing an order with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    order = Order(**data)
    resp = order.capture()

    return jsonify(resp)


@bp.route("/<order_id>", methods=("POST",))
def get_order_details(order_id):
    """Retrieve the status of the order with the given ID.

    Wrapper for Order.get_details.
    """
    data = request.get_json()
    data["order-id"] = order_id
    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Getting the status of an order with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    order = Order(**data)
    resp = order.get_details()

    return jsonify(resp)


@bp.route("/<order_id>/refund", methods=("POST",))
def refund_order(order_id):
    """Refund the order with the given ID.

    Wrapper for Order.refund.
    """
    data = request.get_json()
    data["order-id"] = order_id
    data_filtered = {key: value for key, value in data.items() if value}
    current_app.logger.info(
        f"Refunding an order with (filtered) data = {json.dumps(data_filtered, indent=2)}"
    )

    order = Order(**data)
    resp = order.refund()

    return jsonify(resp)
