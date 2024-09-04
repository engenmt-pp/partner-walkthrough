import {
    onClick,
    createOrder,
    captureOrder,
    createVaultSetupToken,
    createVaultPaymentToken
} from './checkout.js'

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
        // paylater: paypal.FUNDING.PAYLATER,
        venmo: paypal.FUNDING.VENMO,
        alternate: null,
        cards: null,
    }
    // Loop over each payment method

    for (const [label, fundingSource] of Object.entries(fundingSources)) {
        const containerId = `${label}-button-container`
        const container = document.getElementById(containerId)
        if (fundingSource) {
            const methods = getMethods()
            const config = { fundingSource, style, ...methods }

            const button = paypal.Buttons(config)
            if (button.isEligible()) {
                button.render(`#${containerId}`)
            }
            if (label == 'paypal') {
                container.style.display = 'block'
            } else {
                container.style.display = 'none'
            }
        }
        else {
            if (label == 'alternate') {
                document.getElementById('alternate-button-container').style.display = 'none'
            } else if (label == 'cards') {
                const foo = 1
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
            })
        })
}

export {
    loadPaymentMethods as default
}