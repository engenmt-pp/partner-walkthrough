import { addApiCalls, getOptions, setAuthHeader } from "./utils.js";

function populateReferralLink(actionUrl, onboardCompleteCallback) {
  const anchor = document.getElementById("partner-referral");
  anchor.href = `${actionUrl}&displayMode=minibrowser`;

  if (onboardCompleteCallback) {
    anchor.setAttribute("data-paypal-onboard-complete", onboardCompleteCallback);
  }

  if (anchor.getAttribute("style")) {
    anchor.setAttribute("style", "");
  } else {
    addProxyReferral();
  }
}

function addProxyReferral() {
  const proxyAnchor = document.createElement("a");
  proxyAnchor.className = "proxy";
  proxyAnchor.innerHTML = "Begin onboarding";

  const div = document.querySelector("[data-page=onboarding]");
  div.prepend(proxyAnchor);
}

let sellerNonce;
async function createReferral() {
  console.group("Creating the partner referral...");

  const options = getOptions();
  const response = await fetch("/api/partner/referrals", {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify(options),
  });
  const createData = await response.json();
  const { formatted, actionUrl, authHeader } = createData;
  ({ sellerNonce } = createData);
  setAuthHeader(authHeader);
  console.log("Done!");

  if (actionUrl) {
    console.log("Action URL received:", actionUrl);
    addApiCalls(formatted, false);
    const onboardCompleteCallback_ =
      options.party === "first" ? getSellerAccessToken : false;
    window.onboardCompleteCallback = onboardCompleteCallback_;
    populateReferralLink(actionUrl, "onboardCompleteCallback");
  } else {
    console.error("No actionUrl found:", createData);
    addApiCalls(formatted);
  }
  console.groupEnd();
}

async function getSellerAccessToken(authCode, sharedId) {
  console.group("Onboarding complete! This is the callback.");
  console.log("authCode:", authCode);
  console.log("sharedId:", sharedId);
  console.log("Fetching a seller access token...");
  const response = await fetch("/api/identity/seller-access-token", {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify({
      "auth-code": authCode,
      "shared-id": sharedId,
      "seller-nonce": sellerNonce,
    }),
  });
  const { formatted, access_token: accessToken } = await response.json();
  addApiCalls(formatted);
  console.log("Done! access_token:", accessToken);

  getSellerCredentials(accessToken);
  console.groupEnd();
}

async function getSellerCredentials(accessToken) {
  console.group("Using the seller access token to request the seller's credentials...");

  const partnerId = document.getElementById("partner-id").value;
  const response = await fetch("/api/identity/seller-credentials", {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify({
      "partner-id": partnerId,
      "access-token": accessToken,
    }),
  });
  const { formatted } = await response.json();
  addApiCalls(formatted);
  console.log("Done!");
  console.groupEnd();
}

export { createReferral as default };
