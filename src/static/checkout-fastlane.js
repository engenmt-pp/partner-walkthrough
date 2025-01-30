import { addApiCalls, getOptions, setAuthHeader } from "./utils.js";

async function createOrder(singleUseToken) {
  console.group("Creating the order...");

  const options = getOptions();
  if (singleUseToken) {
    options["single-use-token"] = singleUseToken;
    options["payment-source"] = "card";
  } else {
    alert("No singleUseToken received!");
    return;
  }

  const createResp = await fetch("/api/orders/", {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify(options),
  });
  const createData = await createResp.json();
  const { formatted, authHeader, orderId, authId, authStatus, captureId, captureStatus } =
    createData;
  setAuthHeader(authHeader);

  addApiCalls(formatted);
  console.log(`Order ${orderId} created!`);
  if (captureId) {
    console.log(`Capture ${captureId} was ${captureStatus}!`);
  } else {
    console.log(`Authorization ${authId} was ${authStatus}!`);
  }
  console.groupEnd();
  return { orderId, authId, captureId };
}

async function captureOrder({ orderId, authId }) {
  const options = getOptions();
  options["payment-source"] = "card";

  if (authId) {
    console.group(`Capturing authorization ${authId}...`);
    options["auth-id"] = authId;
  } else {
    console.group(`Capturing order ${orderId}...`);
  }

  const captureResp = await fetch(`/api/orders/${orderId}/capture`, {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify(options),
  });

  const captureData = await captureResp.json();
  const { formatted, authHeader, captureStatus } = captureData;
  setAuthHeader(authHeader);
  if (captureStatus) {
    console.log(`Captured order ${orderId}! Capture status: ${captureStatus}`);
  } else {
    console.log(`Unable to capture order.`);
  }

  addApiCalls(formatted);
  console.groupEnd();
}

let fastlane;
let fastlanePaymentComponent;
let identity, profile;
const styles = {
  // root: { backgroundColorPrimary: "#FAFAFA" }
  // root: { backgroundColorPrimary: "#FFF" }
  root: { backgroundColorPrimary: "transparent" },
};

async function attemptCheckout() {
  console.group("Attempting checkout...");
  if (!fastlanePaymentComponent) {
    console.log(
      "The fastlanePaymentComponent is not yet loaded. Load the component by looking up an email first.",
    );
    alert("Fastlane checkout first requires an email address lookup!");
    console.groupEnd();
    return;
  }

  console.log("Facilitating checkout...");
  const { id: paymentTokenId } = await fastlanePaymentComponent.getPaymentToken();

  const { orderId, authId, captureId } = await createOrder(paymentTokenId);

  if (captureId) {
    console.log(`Received capture back from 'create order': ${captureId}`);
  } else {
    console.log("Attempting capture...");
    await captureOrder({ orderId, authId });
  }
}

async function setUpCheckout() {
  const emailContainer = document.getElementById("fastlane-email-container");
  const emailButton = document.getElementById("fastlane-email-button");

  const emailInput = document.getElementById("fastlane-email-input");
  const emailAddress = emailInput?.value;

  if (emailAddress) {
    emailContainer.setAttribute("hidden", true);
    emailContainer.setAttribute("disabled", true);
    emailInput.setAttribute("disabled", true);
    emailButton.classList.toggle("disabled");

    const { customerContextId } = await identity.lookupCustomerByEmail(emailAddress);

    if (customerContextId) {
      await initializeReturnBuyerCheckout(customerContextId);
    } else {
      await initializeGuestBuyerCheckout();
    }
  } else {
    alert("No email found to look up!");
  }

  if (fastlanePaymentComponent) {
    await fastlanePaymentComponent.render("#payment-container");

    const fastlaneWatermark = document.getElementById("watermark-container");
    fastlaneWatermark.classList.toggle("hidden");

    const payButton = document.getElementById("pay-button");
    payButton.classList.toggle("disabled");
  }
}

async function initializeReturnBuyerCheckout(customerContextId) {
  console.group("Initializing return buyer (Ryan) flow...");
  console.log({ customerContextId });

  const { authenticationState, profileData } =
    await identity.triggerAuthenticationFlow(customerContextId);
  console.log("Authentication result:", { authenticationState, profileData });
  if (authenticationState === "succeeded") {
    console.log("Authentication succeeded!");
    const { shippingAddress } = profileData;
    if (shippingAddress) {
      setUpShippingAddress();
      displayShippingAddress(shippingAddress);
    } else {
      alert("No shipping address!");
    }
    fastlanePaymentComponent = await fastlane.FastlanePaymentComponent({
      styles,
    });
  } else {
    console.log("Authentication unsuccessful... falling back to guest experience.");
    console.groupEnd();
    return await initializeGuestBuyerCheckout();
  }
  console.groupEnd();
}

async function initializeGuestBuyerCheckout() {
  console.group("Setting up guest buyer (Gary) flow...");

  const fields = {
    phoneNumber: { prefill: "8882211161" },
    cardholderName: { prefill: "Noauthgary Cardholder" },
  };

  const shippingAddress = {
    name: {
      fullName: "Kat Z.",
    },
    address: {
      addressLine1: "205 E Houston St",
      adminArea2: "New York",
      adminArea1: "NY",
      postalCode: "10002",
      countryCode: "US",
    },
  };

  const options = {
    styles,
    fields,
    shippingAddress,
  };
  console.log("Initializing guest buyer checkout with options:", options);

  fastlanePaymentComponent = await fastlane.FastlanePaymentComponent(options);
  console.groupEnd();
}

async function setUpShippingAddress() {
  async function changeShippingAddress() {
    console.group("Changing shipping address...");
    const { selectionChanged, selectedAddress } =
      await profile.showShippingAddressSelector();

    if (selectionChanged) {
      console.log("Selection changed!");
      displayShippingAddress(selectedAddress);
    } else {
      console.log("No new address selected.");
    }
    console.groupEnd();
  }

  const button = document.getElementById("shipping-address-button");
  button.addEventListener("click", changeShippingAddress);

  const fastlaneWatermark = await fastlane.FastlaneWatermarkComponent({
    includeAdditionalInfo: false,
  });
  fastlaneWatermark.render("#shipping-watermark-container");
}

async function displayShippingAddress(shippingAddress) {
  const { name, address, phoneNumber } = shippingAddress;

  const shippingAddressFooter = document.getElementById("shipping-watermark-container");
  const div = document.createElement("div");

  if (name) div.append(`\n${name.fullName}`);

  if (address) {
    const {
      addressLine1 = "addressLine1",
      addressLine2,
      adminArea1 = "adminArea1",
      adminArea2 = "adminArea2",
      postalCode = "postalCode",
    } = address;

    div.append(`\n${addressLine1}`);

    if (addressLine2) div.append(`\n${addressLine2}\n`);

    div.append(`\n${adminArea2}, ${adminArea1} ${postalCode}\n`);
  }

  if (phoneNumber) {
    const { countryCode = "countryCode", nationalNumber = "nationalNumber" } =
      phoneNumber;
    div.append(`\n+${countryCode} ${nationalNumber}\n`);
  }

  shippingAddressFooter.insertAdjacentElement("beforebegin", div);
}

async function loadFastlane() {
  const cardOptions = { allowedBrands: ["VISA"] };
  const fastlaneConfig = { cardOptions };
  console.log("Instantiating paypal.Fastlane with this config:", fastlaneConfig);
  fastlane = await paypal.Fastlane({ cardOptions });
  console.log("Fastlane:", fastlane);
  ({ identity, profile } = fastlane);

  const fastlaneWatermark = await fastlane.FastlaneWatermarkComponent({
    includeAdditionalInfo: true,
  });
  fastlaneWatermark.render("#watermark-container");

  window.localStorage.setItem("fastlaneEnv", "sandbox");

  const emailLookupButton = document.getElementById("fastlane-email-button");
  emailLookupButton.addEventListener("click", setUpCheckout);
  emailLookupButton.classList.toggle("disabled");

  document.getElementById("pay-button").addEventListener("click", attemptCheckout);
}

export { loadFastlane as default };
