(function () {
    var a = document.getElementById('privacy-back');
    if (!a) return;
    var params = new URLSearchParams(window.location.search);
    var returnUrl = params.get('return_url');
    if (returnUrl) {
        a.href = returnUrl;
        a.textContent = 'Вернуться в приложение';
    } else if (document.referrer && document.referrer.indexOf(window.location.origin) === 0) {
        a.href = document.referrer;
    } else {
        a.href = '/orders/checkout';
    }
})();
