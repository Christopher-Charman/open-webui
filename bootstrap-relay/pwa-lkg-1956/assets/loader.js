(() => {
  'use strict';
  // Bootstrap isolation: custom Continuity/LCARS modules intentionally deferred.
  // Stock OpenWebUI must mount first; enhancements are reintroduced after verified mount.
  window.__CONTINUITY_BOOTSTRAP_ISOLATED__ = true;
})();
