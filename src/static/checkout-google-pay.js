import { createOrder, captureOrder } from "./checkout.js";
import { getOptions } from "./utils.js";

const baseRequest = {
  apiVersion: 2,
  apiVersionMinor: 0,
};
let paymentsClient;
let allowedPaymentMethods;
let merchantInfo;

function getGooglePaymentsClient() {
  /**
   * Load the Google Payments Client or return the already loaded one.
   */
  if (paymentsClient) {
    console.log("Payments client already loaded!");
  } else {
    console.log("Loading payments client...");
    paymentsClient = new google.payments.api.PaymentsClient({
      environment: "TEST",
      paymentDataCallbacks: {
        onPaymentAuthorized: createAndCaptureOrder,
      },
    });
  }
  return paymentsClient;
}
async function getGooglePayConfig() {
  /**
   * Load the Google Pay Config { allowedPaymentMethod, merchantInfo } or return the already loaded config.
   */
  if (allowedPaymentMethods && merchantInfo) {
    console.log("Google Pay config. already loaded!");
  } else {
    console.log("Loading Google Pay config...");
    ({ allowedPaymentMethods, merchantInfo } = await paypal.Googlepay().config());
  }
  const googlePayConfig = { allowedPaymentMethods, merchantInfo };
  console.log("Google Pay config.:", googlePayConfig);
  return googlePayConfig;
}

function getGoogleIsReadyToPayRequest(allowedPaymentMethods) {
  return Object.assign({}, baseRequest, { allowedPaymentMethods });
}
async function getGooglePaymentDataRequest() {
  const { allowedPaymentMethods } = await getGooglePayConfig();

  const paymentDataRequest = Object.assign({}, baseRequest);
  paymentDataRequest.allowedPaymentMethods = allowedPaymentMethods;
  paymentDataRequest.transactionInfo = getGoogleTransactionInfo();
  paymentDataRequest.callbackIntents = ["PAYMENT_AUTHORIZATION"];

  return paymentDataRequest;
}
function getGoogleTransactionInfo() {
  /**
   * Convert the transaction-related form options into fields for Google Pay.
   */

  const formOptions = getOptions();
  let displayItems = [];
  let totalPrice = 0;

  const subtotalPrice = parseFloat(formOptions["item-price"]);
  if (subtotalPrice > 0) {
    displayItems.push({
      label: "Subtotal",
      type: "SUBTOTAL",
      price: subtotalPrice.toFixed(2),
    });
    totalPrice += subtotalPrice;
  }

  const taxPrice = parseFloat(formOptions["item-tax"]);
  if (taxPrice > 0) {
    displayItems.push({
      label: "Tax",
      type: "TAX",
      price: subtotalPrice.toFixed(2),
    });
    totalPrice += taxPrice;
  }

  let countryCode = formOptions["buyer-country-code"];
  if (countryCode == "") {
    countryCode = "US";
  }
  const currencyCode = formOptions["currency-code"];
  return {
    displayItems,
    countryCode,
    currencyCode,
    totalPriceLabel: "Total",
    totalPriceStatus: "FINAL",
    totalPrice: totalPrice.toFixed(2),
  };
}
async function onClick() {
  /**
   * Show Google Pay payment sheet when Google Pay payment button is clicked
   */
  const paymentDataRequest = await getGooglePaymentDataRequest();
  paymentDataRequest.transactionInfo = getGoogleTransactionInfo();

  paymentsClient = getGooglePaymentsClient();
  paymentsClient.loadPaymentData(paymentDataRequest);
}
async function createAndCaptureOrder({ paymentMethodData }) {
  console.group("Creating a PayPal order with paymentMethodData:", paymentMethodData);
  const paymentSource = "google_pay";
  const options = { paymentSource };
  const orderId = await createOrder(options);
  options.orderID = orderId;
  const returnVal = {};
  try {
    console.group("Confirming order with Google...");
    const confirmOrderResponse = await paypal.Googlepay().confirmOrder({
      orderId,
      paymentMethodData,
    });
    console.log("Done! confirmOrderResponse:", confirmOrderResponse);
    if (confirmOrderResponse.status === "APPROVED") {
      console.log("Confirmation approved!");
      const captureStatus = await captureOrder(options);
      if (captureStatus === "COMPLETED") {
        console.log("Capture was successful! 😃 Huzzah!");
        returnVal.transactionState = "SUCCESS";
      } else {
        console.error("Capture was unsuccessful. 😩");
        returnVal.transactionState = "ERROR";
        returnVal.error = {
          intent: "PAYMENT_AUTHORIZATION",
          message: "TRANSACTION FAILED AS CAPTURE STATUS WAS NOT COMPLETED.",
        };
      }
    } else {
      console.error("Confirmation NOT approved. 😩");
      returnVal.transactionState = "ERROR";
      returnVal.error = {
        intent: "PAYMENT_AUTHORIZATION",
        message: "TRANSACTION FAILED AS CONFIRM ORDER RESPONSE STATUS WAS NOT APPROVED",
      };
    }
  } catch (err) {
    console.error("Encountered an error:", err);
    returnVal.transactionState = "ERROR";
    returnVal.error = {
      intent: "PAYMENT_AUTHORIZATION",
      message: err.message,
    };
  } finally {
    console.log("Order complete. returnVal:", returnVal);
    console.groupEnd();
    return returnVal;
  }
}
async function addGooglePayButton() {
  const buttonOptions = {};

  const buttonColor = document.getElementById("google-pay-button-color")?.value;
  if (buttonColor) {
    buttonOptions.buttonColor = buttonColor.toLowerCase();
  }
  const buttonType = document.getElementById("google-pay-button-type")?.value;
  if (buttonType) {
    buttonOptions.buttonType = buttonType.toLowerCase();
  }

  const buttonLocale = document.getElementById("google-pay-button-locale")?.value;
  if (buttonLocale) {
    buttonOptions.buttonLocale = buttonLocale.toLowerCase();
  }

  paymentsClient = getGooglePaymentsClient();
  const button = paymentsClient.createButton({
    onClick,
    ...buttonOptions,
  });
  document.getElementById("checkout-google-pay").appendChild(button);
}

async function loadGooglePay() {
  paymentsClient = getGooglePaymentsClient();
  const { allowedPaymentMethods } = await getGooglePayConfig();
  try {
    const isReadyToPayRequest = getGoogleIsReadyToPayRequest(allowedPaymentMethods);
    const response = await paymentsClient.isReadyToPay(isReadyToPayRequest);
    if (response.result) {
      addGooglePayButton();
    }
  } catch (e) {
    const err = await e.message;
    console.error({ err });
  }
}
export { loadGooglePay as default };
