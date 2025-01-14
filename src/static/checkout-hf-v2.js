import {
  getContingencies,
  createOrder,
  captureOrder,
  createVaultSetupToken,
  createVaultPaymentToken,
  onError
} from './checkout.js'

const style = {
  '.valid': { color: 'green' },
  '.invalid': { color: 'red' }
}

function getMethods() {
  const vaultWithoutPurchase = document.querySelector('#vault-without-purchase:checked')
  if (vaultWithoutPurchase) {
    return {
      createVaultSetupToken,
      onApprove: createVaultPaymentToken,
      onError
    }
  }
  return {
    createOrder,
    onApprove: captureOrder,
    onError
  }
}

function getBillingAddress() {
  const data = {}

  const addressFields = {
    streetAddress: 'billing-address-line-1',
    extendedAddress: 'billing-address-line-2',
    locality: 'billing-address-admin-area-1',
    region: 'billing-address-admin-area-2',
    postalCode: 'billing-address-postal-code',
    countryCode: 'billing-address-country-code',
  }

  for (let [key, id] of Object.entries(addressFields)) {
    const val = document.getElementById(id)?.value
    if (val) {
      if (id === 'billing-address-country-code') {
        data[key] = val.toUpperCase()
      } else {
        data[key] = val
      }
    }
  }

  if (Object.entries(data).length > 0) return data

  return null
}

let cardFields
async function onSubmit(event) {
  event.preventDefault()
  event.stopImmediatePropagation()
  const data = {}

  const vaultWithoutPurchase = document.querySelector('#vault-without-purchase:checked')
  if (!vaultWithoutPurchase) {
    const billingAddress = getBillingAddress();
    if (billingAddress) data.billingAddress = billingAddress
  }

  const contingencies = getContingencies()
  if (contingencies) data.contingencies = contingencies

  console.log('Submitting data:', data)
  cardFields.submit(data)
}
async function loadHostedFields() {
  if (cardFields) await cardFields.close()

  const methods = getMethods()
  cardFields = paypal.CardFields({
    style,
    ...methods
  })
  if (cardFields.isEligible()) {

    const numberField = cardFields.NumberField()
    await numberField.render('#card-number')

    const expiryField = cardFields.ExpiryField()
    await expiryField.render('#expiration-date')

    const cvvField = cardFields.CVVField()
    await cvvField.render('#cvv')

    const nameField = cardFields.NameField()
    await nameField.render('#cardholder-name')

    document.querySelector("#hf-v2-form").addEventListener('submit', onSubmit)
  } else {
    alert("Not eligible for Hosted Fields v2!")
  }
}

export {
  loadHostedFields as default
}