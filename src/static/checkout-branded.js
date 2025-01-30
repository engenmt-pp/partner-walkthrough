import {
  onClick,
  createOrder,
  captureOrder,
  createVaultSetupToken,
  createVaultPaymentToken,
} from "./checkout.js";

function getMethods() {
  const vaultWithoutPurchase = document.querySelector("#vault-without-purchase:checked");
  if (vaultWithoutPurchase) {
    return {
      onClick,
      createVaultSetupToken,
      onApprove: createVaultPaymentToken,
    };
  }
  return {
    onClick,
    createOrder,
    onApprove: captureOrder,
  };
}

function getStyle() {
  const label = document.getElementById("button-label")?.value;
  if (label) {
    return { label };
  }
  return {};
}

function getVaultFlow() {
  return document.getElementById("vault-flow")?.value;
}

let buttons;
async function loadButtons() {
  if (buttons) await buttons.close();
  const style = getStyle();
  const methods = getMethods();
  const config = {
    style,
    ...methods,
  };
  const vaultFlow = getVaultFlow();
  if (vaultFlow === "first-time-buyer") {
    config.displayOnly = ["vaultable"];
  }
  buttons = await paypal.Buttons(config);
  return buttons.render("#paypal-button-container").catch((err) => {
    console.log("Caught an error while rendering PayPal buttons:", err);
  });
}

export { loadButtons as default };
