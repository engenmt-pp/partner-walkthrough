import { addApiCalls, getOptions, setAuthHeader } from "./utils.js";

let orderId;
let authId;

async function createOrder() {
  console.group("Creating the order...");

  console.log("Getting order options...");
  const options = getOptions();
  options["vault-flow"] = "buyer-not-present";

  const paymentSource = document.getElementById("vault-payment-source").value;
  options["payment-source"] = paymentSource;

  const createResp = await fetch("/api/orders/", {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify(options),
  });
  const createData = await createResp.json();
  const { authHeader, formatted } = createData;
  setAuthHeader(authHeader);
  addApiCalls(formatted);

  ({ orderId, authId } = createData);

  if (orderId) {
    console.log(`Order ${orderId} created!`);
    if (authId) {
      console.log(`Order already authorized. Auth. ID: ${authId}`);
    }
  } else {
    console.log("Order creation failed!");
    alert("Order creation failed!");
  }
  console.groupEnd();
}

async function authorizeAndOrCaptureOrder() {
  console.group(`Authorizing and/or capturing order ${orderId}!`);

  const options = getOptions();
  if (authId) {
    options["auth-id"] = authId;
  }

  const captureResp = await fetch(`/api/orders/${orderId}/capture`, {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify(options),
  });
  const captureData = await captureResp.json();
  const { formatted } = captureData;
  addApiCalls(formatted);

  console.groupEnd();
}

async function payWithVaultedPaymentToken() {
  console.group("Initiating buyer-not-present checkout...");

  const paymentTokenId = document.getElementById("vault-id").value;
  if (!paymentTokenId) {
    return alert("A payment token must be provided for buyer-not-present orders!");
  }

  await createOrder();
  if (orderId) {
    if (authId) {
      await authorizeAndOrCaptureOrder();
    } else {
      console.log("Order should be complete!");
    }
  }
  console.groupEnd();
}

export { payWithVaultedPaymentToken as default };
