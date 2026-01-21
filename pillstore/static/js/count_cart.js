document.addEventListener('DOMContentLoaded', () => {
    const cartCounter = document.querySelector('#cart-counter');

    async function postForm(url, data) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams(data),
        });
        if (!resp.ok) {
            if (resp.status === 401) {
                window.location.href = '/auth/?next=' + encodeURIComponent(location.pathname);
            }
            throw new Error('Request failed: ' + resp.status);
        }
        return resp.json();
    }
    async function checkStock(productId, requestedQty, btn = null, block = null) {
        const res = await fetch(`/products/api/stock/${productId}`);
        const data = await res.json();
        const qtyInput = document.querySelector('#quantity-input');
        if (qtyInput && qtyInput.hasAttribute('max')) {
            const inputMax = parseInt(qtyInput.getAttribute('max'), 10) || Infinity;
            if (requestedQty > inputMax) return false;
        }
        if (requestedQty > data.stock) {
            let warning = block?.querySelector('.stock-warning');
            if (!warning) {
                warning = document.createElement('span');
                warning.className = 'px-2 text-warning small fst-italic stock-warning';
                btn?.parentNode?.insertBefore(warning, btn.nextSibling);
            }
            btn.disabled = true;
            return false;
        }
        return true;
    }
    document.querySelectorAll('.js-increase').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const block = btn.closest('.cart-controls');
            const productId = parseInt(block.dataset.productId);
            const qtySpan = block.querySelector('.js-qty');
            const current = parseInt(qtySpan.textContent || '0', 10);

            const stockRes = await fetch(`/products/api/stock/${productId}`);
            const stockData = await stockRes.json();
            if (current >= stockData.stock) {
                let warning = block.querySelector('.stock-overlay-warning');
                if (!warning) {
                    warning = document.createElement('div');
                    warning.className = 'stock-overlay-warning';
                    block.style.position = 'relative';
                    block.appendChild(warning);
                }
                btn.disabled = true;
                return;
            }

            if (!(await checkStock(productId, current + 1, btn, block))) return;

            await postForm('/orders/cart/api/set', {
                product_id: productId,
                quantity: (current + 1).toString()
            });
            location.reload();
        });
    });
    document.querySelectorAll('.js-decrease').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const block = btn.closest('.cart-controls');
            const productId = block.dataset.productId;
            const qtySpan = block.querySelector('.js-qty');
            const current = parseInt(qtySpan.textContent || 0, 10);

            await postForm('/orders/cart/api/set', {
                product_id: productId,
                quantity: Math.max(current - 1, 0).toString()
            });
            location.reload();
        });
    });
    document.querySelectorAll('.js-add-to-cart, #add-to-cart-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const block = btn.closest('.cart-controls') || document.querySelector('.cart-controls');
            const productId = block.dataset.productId;

            let quantity = 1;
            const qtyInput = document.querySelector('#quantity-input');
            if (qtyInput && qtyInput.value) {
                quantity = parseInt(qtyInput.value) || 1;
            }

            if (!(await checkStock(productId, quantity, btn, block))) return;

            await postForm('/orders/cart/api/add', {
                product_id: productId,
                quantity: quantity.toString()
            });
            location.reload();
        });
    });

});


