/**
 * PickleballHub 2.0 — Sports Platform Interactive JavaScript
 * Powers Quick Actions Sheet, Kudos micro-reactions, animated counters,
 * and performance charts.
 */

document.addEventListener("DOMContentLoaded", () => {
  // ── 1. Animated Stat Counters ──────────────────────────────────────────────
  const counterElements = document.querySelectorAll("[data-counter-target]");
  
  if (counterElements.length > 0) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const target = parseFloat(el.getAttribute("data-counter-target")) || 0;
          const isDecimal = el.getAttribute("data-counter-decimal") === "true";
          const suffix = el.getAttribute("data-counter-suffix") || "";
          
          let current = 0;
          const duration = 1000;
          const startTime = performance.now();

          function updateCounter(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out cubic
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const val = current + (target - current) * easeProgress;
            
            el.textContent = (isDecimal ? val.toFixed(2) : Math.round(val)) + suffix;

            if (progress < 1) {
              requestAnimationFrame(updateCounter);
            } else {
              el.textContent = (isDecimal ? target.toFixed(2) : target) + suffix;
            }
          }

          requestAnimationFrame(updateCounter);
          obs.unobserve(el);
        }
      });
    }, { threshold: 0.2 });

    counterElements.forEach(el => observer.observe(el));
  }

  // ── 2. Animated XP Progress Bar ────────────────────────────────────────────
  const xpBars = document.querySelectorAll(".sports-xp-fill");
  xpBars.forEach(bar => {
    const width = bar.getAttribute("data-width") || "0%";
    bar.style.width = "0%";
    setTimeout(() => {
      bar.style.width = width;
    }, 150);
  });

  // ── 3. Kudos / Props Reactions ─────────────────────────────────────────────
  document.querySelectorAll(".kudos-btn").forEach(btn => {
    btn.addEventListener("click", function(e) {
      e.preventDefault();
      const countSpan = this.querySelector(".kudos-count");
      const icon = this.querySelector("i");
      let count = parseInt(countSpan ? countSpan.textContent : "0") || 0;

      if (this.classList.contains("active")) {
        this.classList.remove("active");
        if (countSpan) countSpan.textContent = Math.max(0, count - 1);
      } else {
        this.classList.add("active");
        if (countSpan) countSpan.textContent = count + 1;
        
        // Micro-pop effect
        if (icon) {
          icon.style.transform = "scale(1.4) rotate(-15deg)";
          setTimeout(() => {
            icon.style.transform = "scale(1) rotate(0)";
          }, 200);
        }
      }
    });
  });

  // ── 4. Floating Quick Action Modal / Sheet ─────────────────────────────────
  const quickActionModal = document.getElementById("sports-quick-action-sheet");
  const quickActionFab = document.getElementById("nav-bottom-quick-action");
  const quickActionClose = document.getElementById("close-quick-action-sheet");

  window.openQuickActionSheet = function() {
    if (quickActionModal) {
      quickActionModal.classList.add("active");
      document.body.style.overflow = "hidden";
    }
  };

  window.closeQuickActionSheet = function() {
    if (quickActionModal) {
      quickActionModal.classList.remove("active");
      document.body.style.overflow = "";
    }
  };

  if (quickActionFab) {
    quickActionFab.addEventListener("click", window.openQuickActionSheet);
  }

  if (quickActionClose) {
    quickActionClose.addEventListener("click", window.closeQuickActionSheet);
  }

  if (quickActionModal) {
    quickActionModal.addEventListener("click", (e) => {
      if (e.target === quickActionModal) {
        window.closeQuickActionSheet();
      }
    });
  }

  // ── 5. Sports Dashboard Performance Sparkline Chart ────────────────────────
  const perfCanvas = document.getElementById("playerPerformanceChart");
  if (perfCanvas && typeof Chart !== "undefined") {
    const isDark = document.documentElement.classList.contains("dark-mode");
    const ctx = perfCanvas.getContext("2d");

    // Create subtle gradient for court emerald
    const gradient = ctx.createLinearGradient(0, 0, 0, 160);
    gradient.addColorStop(0, "rgba(16, 185, 129, 0.28)");
    gradient.addColorStop(1, "rgba(16, 185, 129, 0.0)");

    new Chart(ctx, {
      type: "line",
      data: {
        labels: ["W1", "W2", "W3", "W4", "W5", "Current"],
        datasets: [{
          label: "Win Rate %",
          data: [50, 58, 62, 60, 65, 68],
          borderColor: "#10b981",
          borderWidth: 3,
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#10b981",
          pointBorderColor: isDark ? "#111723" : "#ffffff",
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 7
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: isDark ? "rgba(17, 23, 35, 0.95)" : "rgba(255, 255, 255, 0.95)",
            titleColor: isDark ? "#f8fafc" : "#0f172a",
            bodyColor: "#10b981",
            borderColor: isDark ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.1)",
            borderWidth: 1,
            padding: 10,
            displayColors: false,
            callbacks: {
              label: (context) => `Win Rate: ${context.parsed.y}%`
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: isDark ? "#64748b" : "#94a3b8",
              font: { size: 10, weight: 600 }
            }
          },
          y: {
            min: 40,
            max: 100,
            grid: {
              color: isDark ? "rgba(255, 255, 255, 0.04)" : "rgba(0, 0, 0, 0.04)"
            },
            ticks: {
              color: isDark ? "#64748b" : "#94a3b8",
              font: { size: 10, weight: 600 },
              callback: (val) => `${val}%`
            }
          }
        }
      }
    });
  }
});
