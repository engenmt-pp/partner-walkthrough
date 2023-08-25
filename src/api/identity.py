import base64
import json
import requests

from flask import Blueprint, current_app, jsonify, request
from .utils import (
    build_endpoint,
    format_request_and_response,
    random_decimal_string,
    AccessTokenFailed,
)


bp = Blueprint("identity", __name__, url_prefix="/identity")


@bp.route("/client-token", methods=("POST",))
def get_client_token():
    """Retrieve a client token using the GET /v1/identity/generate-token endpoint.

    Docs: https://developer.paypal.com/docs/multiparty/checkout/advanced/integrate/#link-generateclienttoken
    """
    endpoint = build_endpoint("/v1/identity/generate-token")
    headers = build_headers()

    return_val = {}
    formatted = headers["formatted"]
    del headers["formatted"]

    try:
        auth_header = headers["Authorization"]
        return_val["authHeader"] = auth_header
    except KeyError:
        return_val["formatted"] = formatted
        return jsonify(return_val)

    response = requests.post(endpoint, headers=headers)

    formatted["client-token"] = format_request_and_response(response)
    return_val["formatted"] = formatted

    try:
        client_token = response.json()["client_token"]
        return_val["clientToken"] = client_token
    except Exception as exc:
        current_app.logger.error(
            f"Exception encountered when getting client_token: {exc}"
        )

    return jsonify(return_val)


@bp.route("/id-token/", defaults={"customer_id": None}, methods=("GET",))
@bp.route("/id-token/<customer_id>", methods=("GET",))
def get_id_token(customer_id):
    """Request access and ID tokens using the GET /v1/oauth2/token endpoint.

    Docs: https://developer.paypal.com/docs/api/reference/get-an-access-token/
    """
    endpoint = build_endpoint("/v1/oauth2/token")
    headers = {"Content-Type": "application/json", "Accept-Language": "en_US"}

    if request.args.get("include-auth-assertion"):
        auth_assertion = build_auth_assertion()
        headers["PayPal-Auth-Assertion"] = auth_assertion

    data = {
        "ignoreCache": True,
        "grant_type": "client_credentials",
        "response_type": "id_token",
    }

    if customer_id:
        data["target_customer_id"] = customer_id

    client_id = current_app.config["PARTNER_CLIENT_ID"]
    secret = current_app.config["PARTNER_SECRET"]

    response = requests.post(
        endpoint, headers=headers, data=data, auth=(client_id, secret)
    )
    response_dict = response.json()

    formatted = {"access-token": format_request_and_response(response)}
    return_val = {"formatted": formatted}
    try:
        access_token = response_dict["access_token"]
        id_token = response_dict["id_token"]
    except KeyError:
        return return_val

    auth_header = f"Bearer {access_token}"
    return_val["authHeader"] = auth_header
    return_val["idToken"] = id_token

    return jsonify(return_val)


def get_access_token(client_id, secret):
    """Request an access token using the /v1/oauth2/token API.

    Docs: https://developer.paypal.com/docs/api/reference/get-an-access-token/
    """
    endpoint = build_endpoint("/v1/oauth2/token")
    headers = {"Content-Type": "application/json", "Accept-Language": "en_US"}

    data = {"grant_type": "client_credentials", "ignoreCache": True}

    response = requests.post(
        endpoint, headers=headers, data=data, auth=(client_id, secret)
    )
    response_dict = response.json()

    current_app.logger.debug(
        f"<get_access_token> {json.dumps(response_dict, indent=2)}"
    )

    return_val = {}
    try:
        access_token = response_dict["access_token"]
    except KeyError as exc:
        current_app.logger.error(f"Encountered a KeyError: {exc}")
        current_app.logger.error(
            f"response_dict = {json.dumps(response_dict, indent=2)}"
        )
    else:
        return_val["access_token"] = access_token
    finally:
        formatted = format_request_and_response(response)
        return_val["formatted"] = formatted
        return return_val


def build_auth_assertion(client_id, merchant_id):
    """Build and return the PayPal Auth Assertion.

    Docs: https://developer.paypal.com/docs/api/reference/api-requests/#paypal-auth-assertion
    """
    header = {"alg": "none"}
    header_b64 = base64.b64encode(json.dumps(header).encode("ascii"))

    payload = {"iss": client_id, "payer_id": merchant_id}
    payload_b64 = base64.b64encode(json.dumps(payload).encode("ascii"))

    signature = b""
    return b".".join([header_b64, payload_b64, signature])


def build_headers(
    client_id=None,
    secret=None,
    bn_code=None,
    include_bn_code=True,
    include_auth_assertion=False,
    include_request_id=False,
    auth_header=None,
):
    """Build commonly used headers using a new PayPal access token."""

    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
        "Content-Type": "application/json",
    }
    formatted = {}

    if not auth_header:
        if client_id is None or secret is None:
            raise Exception(
                f"Invalid client ID/secret passed:\n{client_id=}\n{secret=}"
            )
        access_token_response = get_access_token(client_id, secret)
        formatted["access-token"] = access_token_response["formatted"]
        try:
            access_token = access_token_response["access_token"]
            auth_header = f"Bearer {access_token}"
        except KeyError as exc:
            current_app.error(
                f"<build_headers> Encountered Exception accessing access_token: {exc}"
            )
            return headers

    headers["formatted"] = formatted
    headers["Authorization"] = auth_header

    if include_request_id:
        request_id = random_decimal_string(10)
        headers["PayPal-Request-Id"] = request_id

    if include_bn_code:
        if bn_code is None:
            raise Exception("No BN code passed!")
        headers["PayPal-Partner-Attribution-Id"] = bn_code

    if include_auth_assertion:
        auth_assertion = build_auth_assertion()
        headers["PayPal-Auth-Assertion"] = auth_assertion

    return headers
