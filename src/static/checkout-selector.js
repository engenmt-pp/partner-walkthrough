import {
    onClick,
    createOrder,
    captureOrder,
    createVaultSetupToken,
    createVaultPaymentToken
} from './checkout.js'

import loadHostedFields from './checkout-hf-v2.js'

function getMethods() {
    const vaultWithoutPurchase = document.querySelector('#vault-without-purchase:checked')
    if (vaultWithoutPurchase) {
        return {
            onClick,
            createVaultSetupToken,
            onApprove: createVaultPaymentToken
        }
    }
    return {
        onClick,
        createOrder,
        onApprove: captureOrder
    }
}

async function loadPaymentMethods() {
    const fundingSources = {
        paypal: paypal.FUNDING.PAYPAL,
        venmo: paypal.FUNDING.VENMO,
        alternate: null,
        cards: null,
    }

    // Loop over each payment method
    for (const [label, fundingSource] of Object.entries(fundingSources)) {
        if (fundingSource) {
            const containerId = `${label}-button-container`
            const container = document.getElementById(containerId)

            const methods = getMethods()
            const config = { fundingSource, ...methods }

            const button = paypal.Buttons(config)
            if (button.isEligible()) {
                button.render(`#${containerId}`)
            }
            container.style.display = 'none'
        }
        else {
            if (label == 'alternate') {
                const containerId = `${label}-button-container`
                const container = document.getElementById(containerId)

                container.style.display = 'none'
            } else if (label == 'cards') {
                loadHostedFields()
                const containerId = `${label}-container`
                const container = document.getElementById(containerId)
                container.style.display = 'block'
            }
        }
    }

    document.querySelectorAll('input[name=payment-option]')
        .forEach(function (elt) {
            const label = elt.value
            elt.addEventListener('change', function (event) {
                console.log('Changed!', event)
                console.log('label', label)
                document.querySelectorAll('div[id$="-button-container"]')
                    .forEach((container) => {
                        if (container.id.startsWith(label)) {
                            console.log(container, 'block')
                            container.style.display = 'block'
                        } else {
                            console.log(container, 'none')
                            container.style.display = 'none'
                        }
                    })
                document.getElementById('cards-container').style.display = (
                    label == 'cards' ? 'block' : 'none'
                )
            })
        })
}

export {
    loadPaymentMethods as default
}