/**
 * Glass Background Interactive Micro-Physics
 * Smooth inertial mouse-parallax for background glass discs.
 */
(function() {
  if (typeof window === 'undefined') return;
  
  var targetX = 0, targetY = 0;
  var currentX = 0, currentY = 0;
  var ticking = false;

  window.addEventListener('mousemove', function(e) {
    var xFactor = (e.clientX / window.innerWidth) - 0.5;
    var yFactor = (e.clientY / window.innerHeight) - 0.5;
    targetX = xFactor * 16; // 16px interactive drift
    targetY = yFactor * 12; // 12px interactive drift
    
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(updatePhysics);
    }
  }, { passive: true });

  function updatePhysics() {
    currentX += (targetX - currentX) * 0.08;
    currentY += (targetY - currentY) * 0.08;
    
    document.documentElement.style.setProperty('--bg-parallax-x', currentX.toFixed(2) + 'px');
    document.documentElement.style.setProperty('--bg-parallax-y', currentY.toFixed(2) + 'px');
    
    if (Math.abs(targetX - currentX) > 0.05 || Math.abs(targetY - currentY) > 0.05) {
      requestAnimationFrame(updatePhysics);
    } else {
      ticking = false;
    }
  }
})();
