// UI helpers: character counter, example chips, nav toggles, password reveal, double-submit guard.
document.addEventListener("DOMContentLoaded", function () {
  var box = document.getElementById("message");
  var counter = document.getElementById("counter");
  if (box && counter) {
    var upd = function () { counter.textContent = box.value.length + " / 500"; };
    box.addEventListener("input", upd); upd();
    document.querySelectorAll(".example").forEach(function (b) {
      b.addEventListener("click", function () { box.value = b.textContent.trim(); upd(); box.focus(); });
    });
  }

  // Mobile top-nav (student / public)
  var nt = document.getElementById("navToggle"), nb = document.getElementById("navBox");
  if (nt && nb) nt.addEventListener("click", function () { nb.classList.toggle("open"); });

  // Warden sidebar drawer on small screens
  var st = document.getElementById("sideToggle"), sb = document.getElementById("sidebar"), sc = document.getElementById("scrim");
  function toggleSide(open) { sb.classList.toggle("open", open); sc.classList.toggle("open", open); }
  if (st && sb && sc) {
    st.addEventListener("click", function () { toggleSide(!sb.classList.contains("open")); });
    sc.addEventListener("click", function () { toggleSide(false); });
  }

  // Show / hide password
  document.querySelectorAll(".pw-toggle").forEach(function (b) {
    b.addEventListener("click", function () {
      var input = b.parentElement.querySelector("input");
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      b.innerHTML = '<i class="bi ' + (show ? "bi-eye-slash" : "bi-eye") + '"></i>';
    });
  });

  // Double-submit guard
  document.querySelectorAll("form").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      var btn = e.submitter || f.querySelector("button:not([type=button])");
      if (btn && !f.dataset.sent) { f.dataset.sent = "1"; setTimeout(function () { btn.classList.add("disabled"); }, 10); }
    });
  });
});
