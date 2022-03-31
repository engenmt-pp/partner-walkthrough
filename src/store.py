import json

from flask import Blueprint, current_app, render_template
from .api import get_order_details

bp = Blueprint("store", __name__, url_prefix="/store")


def apple_pie():
    return {
        "name": "An apple pie",
        "description": "It's a pie made from apples.",
        "price": 3.14,
    }


@bp.route("/checkout")
def checkout(partner_client_id=None, payee_id=None, bn_code=None):
    if partner_client_id is None:
        partner_client_id = current_app.config["PARTNER_CLIENT_ID"]
    if payee_id is None:
        payee_id = current_app.config["MERCHANT_ID"]
    if bn_code is None:
        bn_code = current_app.config["PARTNER_BN_CODE"]

    product = apple_pie()

    return render_template(
        "checkout.html",
        product=product,
        partner_client_id=partner_client_id,
        payee_merchant_id=payee_id,
        bn_code=bn_code,
    )


@bp.route("/checkout-js")
def checkout_ship_js_sdk(partner_client_id=None, payee_id=None, bn_code=None):
    if partner_client_id is None:
        partner_client_id = current_app.config["PARTNER_CLIENT_ID"]
    if payee_id is None:
        payee_id = current_app.config["MERCHANT_ID"]
    if bn_code is None:
        bn_code = current_app.config["PARTNER_BN_CODE"]

    product = apple_pie()

    return render_template(
        "checkout-ship-api.html",
        product=product,
        partner_client_id=partner_client_id,
        payee_id=payee_id,
        bn_code=bn_code,
    )


@bp.route("/checkout-api")
def checkout_ship_api():
    product = apple_pie()

    return render_template(
        "checkout-ship-api.html",
        product=product,
        partner_client_id=PARTNER_CLIENT_ID,
        payee_merchant_id=MERCHANT_ID,
        bn_code=PARTNER_BN_CODE,
    )


@bp.route("/order-details/<order_id>")
def order_details(order_id):
    order_details_dict = get_order_details(order_id)
    order_details_str = json.dumps(order_details_dict, indent=2)
    return render_template("status.html", status=order_details_str)
