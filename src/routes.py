from flask import Blueprint, current_app, render_template, request

bp = Blueprint("routes", __name__, url_prefix="/")


def get_partner_and_merchant_config(is_fastlane=False, is_direct_merchant=False):
    if is_fastlane:
        if is_direct_merchant:
            return {
                "partner_id": current_app.config["FASTLANE_MERCHANT_ID"],
                "partner_client_id": current_app.config["FASTLANE_MERCHANT_CLIENT_ID"],
                "partner_bn_code": current_app.config["FASTLANE_MERCHANT_BN_CODE"],
                "merchant_id": current_app.config["FASTLANE_MERCHANT_ID"],
            }
        else:
            return {
                "partner_id": current_app.config["FASTLANE_PARTNER_ID"],
                "partner_client_id": current_app.config["FASTLANE_PARTNER_CLIENT_ID"],
                "partner_bn_code": current_app.config["FASTLANE_PARTNER_BN_CODE"],
                "merchant_id": current_app.config["FASTLANE_MERCHANT_ID"],
            }
    else:
        return {
            "partner_id": current_app.config["PARTNER_ID"],
            "partner_client_id": current_app.config["PARTNER_CLIENT_ID"],
            "partner_bn_code": current_app.config["PARTNER_BN_CODE"],
            "merchant_id": current_app.config["MERCHANT_ID"],
        }


@bp.route("onboarding/")
def onboarding():
    """Return the rendered onboarding page from its template."""

    template = "onboarding.html"
    partner_config = get_partner_and_merchant_config()
    del partner_config["merchant_id"]

    return render_template(
        template,
        **partner_config,
        favicon=current_app.config["favicon"],
    )


@bp.route("")
@bp.route("checkout/", endpoint="checkout-canonical")
@bp.route("checkout/branded/")
def checkout_branded():
    """Return the rendered Branded checkout page from its template."""

    template = "checkout-branded.html"
    partner_and_merchant_config = get_partner_and_merchant_config()

    return render_template(
        template,
        method="branded",
        **partner_and_merchant_config,
        favicon=current_app.config["favicon"],
    )


@bp.route("checkout/selector/")
def checkout_selector():
    """Return the rendered branded+ACDC checkout page from its template."""

    template = "checkout-selector.html"
    partner_and_merchant_config = get_partner_and_merchant_config()

    return render_template(
        template,
        method="selector",
        **partner_and_merchant_config,
        favicon=current_app.config["favicon"],
    )


@bp.route("checkout/google-pay/")
def checkout_google_pay():
    """Return the rendered Google Pay checkout page from its template."""

    template = "checkout-google-pay.html"
    partner_and_merchant_config = get_partner_and_merchant_config()

    return render_template(
        template,
        method="google-pay",
        **partner_and_merchant_config,
        favicon=current_app.config["favicon"],
    )


@bp.route("checkout/hosted-v1/")
def checkout_hosted_v1():
    """Return the rendered Hosted Fields v1 checkout page from its template."""

    template = "checkout-hf-v1.html"
    partner_and_merchant_config = get_partner_and_merchant_config()

    return render_template(
        template,
        method="hosted-v1",
        **partner_and_merchant_config,
        favicon=current_app.config["favicon"],
    )


@bp.route("checkout/hosted-v2/")
def checkout_hosted_v2():
    """Return the rendered Hosted Fields v2 checkout page from its template."""

    template = "checkout-hf-v2.html"
    partner_and_merchant_config = get_partner_and_merchant_config()

    return render_template(
        template,
        method="hosted-v2",
        **partner_and_merchant_config,
        favicon=current_app.config["favicon"],
    )


@bp.route("checkout/fastlane/")
def checkout_fastlane():
    """Return the rendered Fastlane checkout page from its template."""

    template = "checkout-fastlane.html"

    is_direct_merchant = request.args.get("PPCP") == "direct-merchant"
    partner_and_merchant_config = get_partner_and_merchant_config(
        is_fastlane=True, is_direct_merchant=is_direct_merchant
    )

    return render_template(
        template,
        method="fastlane",
        **partner_and_merchant_config,
        favicon=current_app.config["favicon"],
    )


@bp.route("statuses/")
def statuses():
    """Return the rendered statuses page from its template."""

    template = "statuses.html"
    partner_and_merchant_config = get_partner_and_merchant_config()

    return render_template(
        template,
        **partner_and_merchant_config,
        favicon=current_app.config["favicon"],
    )
