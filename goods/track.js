// アプリのどの導線から来たかを計測する。
// アプリ側は ?from=magazine (月刊誌 巻末) / ?from=toolbox (よみもの 道具箱) を付けて開く。
// 個人情報 (名前・犬種・年齢) は URL に一切含めない — Pick.swift の PickPlacement を参照。
//
// TODO: GA4 の計測タグを <head> に入れると、以下がそのまま送られます。
//   <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXX"></script>
//   <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}
//   gtag('js',new Date());gtag('config','G-XXXXXXX');</script>
(function () {
  var from = new URLSearchParams(location.search).get('from') || 'direct';
  document.addEventListener('DOMContentLoaded', function () {
    if (typeof gtag === 'function') gtag('event', 'goods_view', { wandary_from: from });
    document.querySelectorAll('a[data-outbound]').forEach(function (a) {
      a.addEventListener('click', function () {
        if (typeof gtag === 'function') {
          gtag('event', 'outbound_click', { wandary_from: from, product: a.dataset.outbound });
        }
      });
    });
  });
})();
