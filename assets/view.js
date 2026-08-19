/* 首页视图切换：按时间 / 按分类（同一页，只换排序） */
(function () {
  function setView(v) {
    var t = document.getElementById('view-time');
    var c = document.getElementById('view-category');
    if (t) t.style.display = (v === 'time') ? '' : 'none';
    if (c) c.style.display = (v === 'category') ? '' : 'none';
  }
  function current() {
    return location.hash === '#category' ? 'category' : 'time';
  }
  window.addEventListener('hashchange', function () { setView(current()); });
  setView(current());
})();
