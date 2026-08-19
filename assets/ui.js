/* 界面小功能：相对时间显示 + 返回顶部按钮 */
(function () {
  // ---------- 相对时间：列表里显示「3 天前」，鼠标悬停显示完整日期 ----------
  function relative(dateStr) {
    var d = new Date(dateStr.replace(/-/g, "/"));
    if (isNaN(d.getTime())) return null;
    var diff = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diff < 0) return null;                       // 未来日期不动
    if (diff < 3600) return "刚刚";
    if (diff < 86400) return Math.floor(diff / 3600) + " 小时前";
    var day = Math.floor(diff / 86400);
    if (day === 1) return "昨天";
    if (day < 30) return day + " 天前";
    var mon = Math.floor(day / 30);
    if (mon < 12) return mon + " 个月前";
    return Math.floor(day / 365) + " 年前";
  }

  document.querySelectorAll("time.post-date[data-date]").forEach(function (el) {
    var full = el.getAttribute("data-date");
    var rel = relative(full);
    if (rel) {
      el.textContent = rel;
      el.title = full;
      el.classList.add("is-relative");
    }
  });

  // ---------- 返回顶部 ----------
  var btn = document.getElementById("to-top");
  if (!btn) return;
  function toggle() {
    if (window.scrollY > 420) btn.classList.add("show");
    else btn.classList.remove("show");
  }
  window.addEventListener("scroll", toggle, { passive: true });
  btn.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  toggle();
})();
