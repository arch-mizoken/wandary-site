// アクセス解析。測定IDを**この1か所**だけで持つ。
//
// ページは全部 <script src="/ga.js"> を読むので、ID を替えるのはここだけ。
// head に直接貼ると、手書きのページ8枚と生成テンプレート5つに同じ文字列が
// 散って、次に替えるときに必ずどれかが取り残される。
//
// ID が空のあいだ、このファイルは**何もしません。**計測タグも読み込みません。
var WANDARY_GA = '';   // 例: 'G-XXXXXXXXXX'

(function () {
  if (!WANDARY_GA) return;

  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  gtag('js', new Date());
  gtag('config', WANDARY_GA);

  // 計測タグ本体。defer で読んでいるので、ここでの挿入は
  // DOMContentLoaded より前に走る (track.js が gtag を見つけられる)
  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + WANDARY_GA;
  document.head.appendChild(s);
})();
