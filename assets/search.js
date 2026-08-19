/* 首页搜索：按标题 / 标签 / 简介实时过滤，空分类组自动隐藏（两个视图通用） */
(function () {
  var input = document.getElementById('site-search');
  if (!input) return;
  input.addEventListener('input', function () {
    var q = this.value.trim().toLowerCase();
    document.querySelectorAll('.post-row').forEach(function (r) {
      var hit = !q || (r.textContent || '').toLowerCase().indexOf(q) !== -1;
      r.style.display = hit ? '' : 'none';
    });
    document.querySelectorAll('.post-group').forEach(function (g) {
      var any = false;
      g.querySelectorAll('.post-row').forEach(function (r) {
        if (r.style.display !== 'none') any = true;
      });
      g.style.display = any ? '' : 'none';
    });
  });
})();
