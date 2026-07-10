// main.js — students will add JavaScript here as features are built

document.addEventListener("DOMContentLoaded", function () {
    var rangeSelect = document.getElementById("range");
    var customDates = document.getElementById("filter-dates");

    if (!rangeSelect || !customDates) return;

    function toggleCustomDates() {
        customDates.classList.toggle("is-hidden", rangeSelect.value !== "custom");
    }

    rangeSelect.addEventListener("change", toggleCustomDates);
    toggleCustomDates();
});
