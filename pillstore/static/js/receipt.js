if (window.location.search.includes('print=1')) {
    window.print();
}
(function () {
    var btn = document.getElementById('receipt-print-btn');
    if (btn) btn.addEventListener('click', function () { window.print(); });
})();
