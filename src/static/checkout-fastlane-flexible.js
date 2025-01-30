import {
  addApiCalls,
  getOptions,
  setOptions,
  loadOptions,
  setAuthHeader,
  saveOptionsAndReloadPage,
} from "./utils.js";
import { buildScriptElement, setupEventListeners } from "./checkout.js";

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

class FastlaneFlexibleCheckout {
  config = {
    cardOptions: { allowedBrands: ["VISA"] },
    styles: {
      root: {
        backgroundColorPrimary: "transparent",
      },
    },
  };
  fastlane;

  constructor() {
    window.localStorage.setItem("fastlaneEnv", "sandbox");
  }

  get emailInput() {
    return document.getElementById("fastlane-email-input");
  }
  get emailContainer() {
    return document.getElementById("fastlane-email-container");
  }
  get emailAddress() {
    return this.emailInput?.value;
  }
  get watermarkId() {
    return "watermark-container";
  }
  get watermarkContainer() {
    return document.getElementById(this.watermarkId);
  }

  async initializeFastlane() {
    console.group("Initializing Fastlane...");
    console.log("Configuration: ", this.config);

    this.fastlane = await paypal.Fastlane(this.config);
    console.log({ fastlane: this.fastlane });

    document.getElementById("fastlane-email-button").removeAttribute("disabled");

    this.initializeWatermark();
    console.groupEnd();
  }

  async initializeWatermark() {
    const includeAdditionalInfo = true;
    console.log(
      "Initializing watermark, " +
        (includeAdditionalInfo ? "" : "not ") +
        "including additional info.",
    );
    this.watermark = await this.fastlane.FastlaneWatermarkComponent({
      includeAdditionalInfo,
    });
    this.watermark.render(`#${this.watermarkId}`);
  }

  async attemptEmailLookup() {
    const { emailAddress } = this;
    if (emailAddress) {
      const { emailContainer } = this;
      emailContainer.setAttribute("disabled", true);
      emailContainer.setAttribute("hidden", true);
      await this.lookupEmail(emailAddress);
    } else {
      alert("No email found to look up!");
    }
  }

  async lookupEmail(emailAddress) {
    const { identity } = this.fastlane;
    const { customerContextId } = await identity.lookupCustomerByEmail(emailAddress);

    this.watermarkContainer.classList.toggle("hidden", true);

    if (customerContextId && (await this.authenticateFastlaneMember(customerContextId))) {
      await this.renderAcceleratedCheckout();
    } else {
      await this.renderGuestCheckout();
    }

    document.getElementById("pay-button").removeAttribute("disabled");
  }

  async authenticateFastlaneMember(customerContextId) {
    console.group("Authenticating Fastlane member...");
    console.log({ customerContextId });

    const { authenticationState, profileData } =
      await this.fastlane.identity.triggerAuthenticationFlow(customerContextId);

    console.info("Authentication result:", { authenticationState, profileData });
    if (profileData) {
      this.profileData = profileData;
    }
    console.groupEnd();
    return authenticationState === "succeeded";
  }

  async renderGuestCheckout() {
    console.group("Rendering guest (Gary) Fastlane flow...");

    const fields = {
      phoneNumber: {
        prefill: "8882211161",
        enabled: false,
      },
      cardholderName: {
        prefill: "Noauthgary Cardholder",
        enabled: true,
      },
    };

    const options = { fields };
    console.info("Config:", options);

    this.cardComponent = await this.fastlane.FastlaneCardComponent(options);
    this.cardComponent.render("#fastlane-card-container");
    console.groupEnd();
  }

  async renderAcceleratedCheckout() {
    console.group("Rendering accelerated (Ryan) Fastlane flow...");

    /* Render
    - the selected card from the profile object
    - the Fastlane watermark
    - the change card button that invokes showCardSelector()
    */
    console.groupEnd();
  }

  async attemptCheckout() {
    const { id: paymentTokenId } = await this.cardComponent.getPaymentToken({
      billingAddress: {
        addressLine1: "2211 North 1st St",
        adminArea1: "CA",
        adminArea2: "San Jose",
        postalCode: "95131",
        countryCode: "US",
      },
    });
    const { orderId, authId, captureId } = await createOrder(paymentTokenId);
    console.log(await orderId);

    if (captureId) {
      console.log(`Received capture back from 'create order': ${captureId}`);
    } else {
      console.log("Attempting capture...");
      await captureOrder({ orderId, authId });
    }
  }
}

window.addEventListener("load", async function () {
  const options = loadOptions();
  window.sessionStorage.clear();
  setOptions(options);

  const fastlane = new FastlaneFlexibleCheckout();
  const loadFastlane = async () => {
    await fastlane.initializeFastlane();

    const emailLookupButton = document.getElementById("fastlane-email-button");
    emailLookupButton.addEventListener("click", () => {
      fastlane.attemptEmailLookup();
    });

    const payButton = document.getElementById("pay-button");
    payButton.addEventListener("click", async () => {
      await fastlane.attemptCheckout();
    });
  };

  buildScriptElement(loadFastlane, "fastlane");
  setupEventListeners(() => {
    buildScriptElement(loadFastlane, "fastlane");
  });

  document.getElementById("ppcp-type").addEventListener("change", (event) => {
    console.log("change", event);
    if (document.querySelector("#ppcp-type > option[value='partner']:checked")) {
      console.log("Partner time!");
      saveOptionsAndReloadPage();
    } else {
      console.log("Direct merchant time!");
      saveOptionsAndReloadPage("direct-merchant");
    }
  });
});
