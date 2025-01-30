import {
  createOrder,
  getCardholderName,
  getContingencies,
  getStatus,
  captureOrder,
} from "./checkout.js";

const styles = {
  ".number": {
    "font-family": "monospace",
  },
  ".valid": { color: "green" },
  ".invalid": { color: "red" },
};
const fields = {
  number: {
    selector: "#card-number",
    placeholder: "4111 1111 1111 1111",
  },
  cvv: {
    selector: "#cvv",
    placeholder: "123",
  },
  expirationDate: {
    selector: "#expiration-date",
    placeholder: "MM/YY",
  },
};

function getBillingAddress() {
  const data = {};

  const addressFields = {
    streetAddress: "billing-address-line-1",
    extendedAddress: "billing-address-line-2",
    locality: "billing-address-admin-area-1",
    region: "billing-address-admin-area-2",
    postalCode: "billing-address-postal-code",
    countryCodeAlpha2: "billing-address-country-code",
  };

  for (let [key, id] of Object.entries(addressFields)) {
    const val = document.getElementById(id)?.value;
    if (val) {
      if (id === "billing-address-country-code") {
        data[key] = val.toUpperCase();
      } else {
        data[key] = val;
      }
    }
  }

  if (Object.entries(data).length > 0) return data;

  return null;
}

let hostedFields;
async function onSubmit(event) {
  event.preventDefault();

  const data = {};

  const billingAddress = getBillingAddress();
  if (billingAddress) data.billingAddress = billingAddress;

  const cardholderName = getCardholderName();
  if (cardholderName) data.cardholderName = cardholderName;

  const contingencies = getContingencies();
  if (contingencies) data.contingencies = contingencies;

  console.log("Submitting data:", data);
  await hostedFields.submit(data);

  await getStatus();
  await captureOrder();
}
async function loadHostedFields() {
  if (paypal.HostedFields.isEligible()) {
    hostedFields = await paypal.HostedFields.render({
      createOrder,
      fields,
      styles,
    });
    const payButton = document.getElementById("pay-button");
    payButton.disabled = false;
    document.getElementById("hf-v1-form").onsubmit = onSubmit;
  } else {
    alert("Not eligible for hosted fields. Sorry!");
    document.getElementById("hf-v1-form").style = "display: none";
  }
}

export { loadHostedFields as default };
