(function () {
    const STORAGE_KEY = 'pillstore_favorites';
    const TOGGLE_URL = '/profile/favorites/toggle';
    const MERGE_URL = '/api/v2/favorites/merge';

    function getGuestFavorites() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return [];
            const arr = JSON.parse(raw);
            return Array.isArray(arr) ? arr.map(Number).filter(Boolean) : [];
        } catch {
            return [];
        }
    }

    function setGuestFavorites(ids) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    }

    function getContainer() {
        return document.getElementById('products-grid') || document.getElementById('product-detail-favorites');
    }

    function isLoggedIn() {
        const el = getContainer();
        return el && el.getAttribute('data-user-logged-in') === '1';
    }

    function getServerFavoriteIds() {
        const el = getContainer();
        if (!el) return [];
        const raw = el.getAttribute('data-favorite-ids') || '';
        if (!raw.trim()) return [];
        return raw.split(',').map(Number).filter(Boolean);
    }

    function getCurrentFavoriteIds() {
        if (isLoggedIn()) return getServerFavoriteIds();
        return getGuestFavorites();
    }

    function setHeartState(btn, inFavorites) {
        const icon = btn.querySelector('i.fa-heart');
        if (!icon) return;
        icon.classList.toggle('text-danger', inFavorites);
        icon.classList.toggle('text-muted', !inFavorites);
    }

    function applyInitialStates() {
        const ids = getCurrentFavoriteIds();
        document.querySelectorAll('.btn-favorite').forEach(function (btn) {
            const productId = parseInt(btn.getAttribute('data-product-id'), 10);
            setHeartState(btn, ids.indexOf(productId) !== -1);
        });
    }

    async function mergeGuestFavoritesAfterLogin() {
        if (!isLoggedIn()) return;
        const localIds = getGuestFavorites();
        if (localIds.length === 0) return;
        try {
            const res = await fetch(MERGE_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ product_ids: localIds }),
            });
            if (res.ok) {
                setGuestFavorites([]);
                const data = await res.json();
                const el = getContainer();
                if (el && data.product_ids) el.setAttribute('data-favorite-ids', data.product_ids.join(','));
                applyInitialStates();
            }
        } catch (_) {}
    }

    async function toggleLoggedIn(productId) {
        const form = new FormData();
        form.append('product_id', String(productId));
        const res = await fetch(TOGGLE_URL, {
            method: 'POST',
            credentials: 'same-origin',
            body: form,
        });
        if (!res.ok) {
            if (res.status === 401) window.location.href = '/auth/?next=' + encodeURIComponent(location.pathname);
            return;
        }
        const data = await res.json();
        return data.in_favorites;
    }

    function toggleGuest(productId) {
        const ids = getGuestFavorites();
        const idx = ids.indexOf(productId);
        if (idx === -1) ids.push(productId);
        else ids.splice(idx, 1);
        setGuestFavorites(ids);
        return ids.indexOf(productId) !== -1;
    }

    async function onFavoriteClick(e) {
        const btn = e.currentTarget;
        if (!btn || !btn.classList.contains('btn-favorite')) return;
        e.preventDefault();
        e.stopPropagation();
        const productId = parseInt(btn.getAttribute('data-product-id'), 10);
        if (!productId) return;

        let inFavorites;
        if (isLoggedIn()) {
            inFavorites = await toggleLoggedIn(productId);
            if (inFavorites === undefined) return;
        } else {
            inFavorites = toggleGuest(productId);
        }
        setHeartState(btn, inFavorites);
    }

    document.addEventListener('DOMContentLoaded', function () {
        applyInitialStates();
        mergeGuestFavoritesAfterLogin();
        document.querySelectorAll('.btn-favorite').forEach(function (btn) {
            btn.addEventListener('click', onFavoriteClick);
        });
    });
})();
