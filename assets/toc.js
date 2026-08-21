/* 文章顶部章间导航：上一章 / 下一章（基于 h2/h3 扫描）；
   首章禁用上一章、末章禁用下一章；右侧标题保持文章标题不变 */
(function () {
  var prev = document.getElementById('tocPrev');
  var next = document.getElementById('tocNext');
  if (!prev || !next) return;

  var heads = Array.prototype.slice.call(
    document.querySelectorAll('.post-body h2, .post-body h3')
  );

  // 无章节：仅隐藏翻页按钮
  if (heads.length < 1) {
    prev.style.display = 'none';
    next.style.display = 'none';
    return;
  }

  function slug(s, i) {
    return 'sec-' + i + '-' + (s || '').trim().slice(0, 24)
      .replace(/\s+/g, '-').replace(/[^\w\u4e00-\u9fa5-]/g, '');
  }
  heads.forEach(function (h, i) {
    if (!h.id) h.id = slug(h.textContent, i);
  });

  var idx = 0;
  function render() {
    prev.disabled = (idx === 0);
    next.disabled = (idx === heads.length - 1);
    prev.title = (idx === 0) ? '已经是第一章了' : '上一章';
    next.title = (idx === heads.length - 1) ? '已经是最后一章了' : '下一章';
  }
  function go(i) {
    idx = Math.max(0, Math.min(heads.length - 1, i));
    var h = heads[idx];
    if (h.scrollIntoView) h.scrollIntoView({ behavior: 'smooth', block: 'start' });
    render();
  }
  prev.addEventListener('click', function () { if (!prev.disabled) go(idx - 1); });
  next.addEventListener('click', function () { if (!next.disabled) go(idx + 1); });

  // 滚动时同步当前章（仅更新上下章按钮的禁用态，右侧标题保持文章标题）
  if ('IntersectionObserver' in window) {
    var visible = [];
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var i = heads.indexOf(e.target);
        if (i < 0) return;
        if (e.isIntersecting) { if (visible.indexOf(i) < 0) visible.push(i); }
        else { visible = visible.filter(function (x) { return x !== i; }); }
      });
      if (visible.length) {
        var top = visible.reduce(function (a, b) { return a < b ? a : b; });
        if (top !== idx) { idx = top; render(); }
      }
    }, { rootMargin: '-60px 0px -65% 0px' });
    heads.forEach(function (h) { obs.observe(h); });
  }
  render();
})();
