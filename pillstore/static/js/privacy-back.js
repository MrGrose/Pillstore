(function () {
    var a = document.getElementById('privacy-back');
    if (a && document.referrer && document.referrer.indexOf(window.location.origin) === 0) {
        a.href = document.referrer;
    }
})();
