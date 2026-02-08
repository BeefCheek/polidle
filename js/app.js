/* ==========================================================
   POLIDLE — Game Logic
   ========================================================== */

(function () {
  "use strict";

  // ----------------------------------------------------------
  // Party color map  (sigle → { name, color })
  // Covers both Assemblée Nationale & Sénat groups (2024-2026).
  // Unknown groups get an auto-generated color.
  // ----------------------------------------------------------
  const PARTY_COLORS = {
    /* --- Assemblée Nationale (17e législature) --- */
    "RN":      { name: "Rassemblement National",                           color: "#0D378A" },
    "EPR":     { name: "Ensemble pour la République",                      color: "#7B4FBE" },
    "LFI-NFP": { name: "La France insoumise – NFP",                       color: "#CC2443" },
    "DR":      { name: "Droite Républicaine",                              color: "#0077CC" },
    "Dem":     { name: "Les Démocrates",                                   color: "#FF8C00" },
    "HOR":     { name: "Horizons & Indépendants",                         color: "#00B4D8" },
    "SOC":     { name: "Socialistes et apparentés",                        color: "#FF6B81" },
    "GDR":     { name: "Gauche Démocrate et Républicaine",                 color: "#BB0000" },
    "LIOT":    { name: "Libertés, Indépendants, Outre-mer et Territoires", color: "#D4A017" },
    "EcoS":    { name: "Écologiste et Social",                             color: "#00A86B" },
    "UDR":     { name: "Union des droites pour la République",             color: "#1B3A5C" },
    "NI":      { name: "Non inscrit",                                      color: "#808080" },

    /* --- Sénat --- */
    "LR":      { name: "Les Républicains",                                 color: "#0066AA" },
    "SER":     { name: "Socialiste, Écologiste et Républicain",            color: "#E05080" },
    "UC":      { name: "Union Centriste",                                  color: "#00A0D2" },
    "RDPI":    { name: "Rassemblement des démocrates, progressistes et indépendants", color: "#DAA520" },
    "CRCE-K":  { name: "Communiste Républicain Citoyen Écologiste – Kanaky", color: "#C40000" },
    "RDSE":    { name: "Rassemblement Démocratique et Social Européen",    color: "#E6A817" },
    "GEST":    { name: "Écologiste – Solidarité et Territoires",           color: "#2ECC71" },
    "INDEP":   { name: "Les Indépendants – République et Territoires",     color: "#8B6914" },
  };

  // ----------------------------------------------------------
  // State
  // ----------------------------------------------------------
  let deputes = [];
  let senateurs = [];
  let pool = [];          // current play pool (shuffled)
  let currentIndex = 0;
  let score = 0;
  let total = 0;
  let streak = 0;
  let bestStreak = 0;
  let mode = "both";
  let answered = false;
  let parties = [];       // unique sigles in pool, sorted

  // ----------------------------------------------------------
  // DOM refs
  // ----------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const els = {
    loading:       $("loading"),
    errorScreen:   $("error-screen"),
    errorMessage:  $("error-message"),
    app:           $("app"),
    score:         $("score"),
    total:         $("total"),
    streak:        $("streak"),
    bestStreak:    $("best-streak"),
    photo:         $("politician-photo"),
    photoCard:     $("photo-card"),
    photoPlaceholder: $("photo-placeholder"),
    chamberBadge:  $("chamber-badge"),
    partyGrid:     $("party-grid"),
    nextBtn:       $("next-btn"),
    answerReveal:  $("answer-reveal"),
    revealIcon:    $("reveal-icon"),
    revealName:    $("reveal-name"),
    revealGroup:   $("reveal-group"),
  };

  // ----------------------------------------------------------
  // Init
  // ----------------------------------------------------------
  async function init() {
    try {
      const [depRes, senRes] = await Promise.all([
        fetch("data/deputes.json").then((r) => {
          if (!r.ok) throw new Error("deputes " + r.status);
          return r.json();
        }),
        fetch("data/senateurs.json").then((r) => {
          if (!r.ok) throw new Error("senateurs " + r.status);
          return r.json();
        }),
      ]);
      deputes = (depRes || []).filter((p) => p.photo);
      senateurs = (senRes || []).filter((p) => p.photo);
    } catch (err) {
      console.error("Data load error:", err);
      // Try loading individually – one may succeed
      try {
        const r = await fetch("data/deputes.json");
        if (r.ok) deputes = await r.json();
      } catch (_) {}
      try {
        const r = await fetch("data/senateurs.json");
        if (r.ok) senateurs = await r.json();
      } catch (_) {}
    }

    if (deputes.length === 0 && senateurs.length === 0) {
      els.loading.classList.add("hidden");
      els.errorScreen.classList.remove("hidden");
      return;
    }

    // Restore persisted state
    bestStreak = parseInt(localStorage.getItem("polidle-best") || "0", 10);

    // Wire events
    setupModeButtons();
    els.nextBtn.addEventListener("click", nextPolitician);
    document.addEventListener("keydown", handleKeydown);

    // Default mode
    setMode("both");

    // Reveal UI
    els.loading.classList.add("hidden");
    els.app.classList.remove("hidden");
  }

  // ----------------------------------------------------------
  // Mode switching
  // ----------------------------------------------------------
  function setupModeButtons() {
    document.querySelectorAll(".mode-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        setMode(btn.dataset.mode);
      });
    });
  }

  function setMode(newMode) {
    mode = newMode;

    switch (mode) {
      case "deputes":
        pool = [...deputes];
        break;
      case "senateurs":
        pool = [...senateurs];
        break;
      default:
        pool = [...deputes, ...senateurs];
    }

    // Compute unique party list
    parties = [...new Set(pool.map((p) => p.groupe_sigle))].filter(Boolean).sort();

    // Reset game
    shuffle(pool);
    currentIndex = 0;
    score = 0;
    total = 0;
    streak = 0;
    updateScoreDisplay();

    nextPolitician();
  }

  // ----------------------------------------------------------
  // Game flow
  // ----------------------------------------------------------
  function nextPolitician() {
    if (pool.length === 0) return;

    if (currentIndex >= pool.length) {
      shuffle(pool);
      currentIndex = 0;
    }

    answered = false;
    const pol = pool[currentIndex];

    // Photo — if it fails to load, skip to next politician
    els.photo.style.display = "block";
    els.photoPlaceholder.classList.add("hidden");
    els.photo.alt = "?";
    els.photo.onerror = function () {
      // Remove this politician from the pool so they never appear again
      pool.splice(currentIndex, 1);
      if (pool.length === 0) return;
      if (currentIndex >= pool.length) currentIndex = 0;
      nextPolitician();
    };
    els.photo.src = pol.photo;

    // Chamber badge
    if (mode === "both") {
      els.chamberBadge.textContent = pol.type === "depute" ? "Assemblée" : "Sénat";
      els.chamberBadge.className = pol.type === "depute" ? "badge-depute" : "badge-senateur";
      els.chamberBadge.style.display = "";
    } else {
      els.chamberBadge.style.display = "none";
    }

    // Hide answer / next
    els.answerReveal.classList.add("hidden");
    els.answerReveal.classList.remove("correct-reveal", "wrong-reveal");
    els.nextBtn.classList.add("hidden");

    // Party buttons
    renderPartyButtons();

    // Entrance animation
    els.photoCard.classList.remove("photo-enter");
    void els.photoCard.offsetWidth; // reflow
    els.photoCard.classList.add("photo-enter");
  }

  function renderPartyButtons() {
    els.partyGrid.innerHTML = "";

    parties.forEach((sigle) => {
      const cfg = getPartyConfig(sigle);

      const btn = document.createElement("button");
      btn.className = "party-btn";
      btn.style.setProperty("--party-color", cfg.color);
      btn.innerHTML =
        '<span class="party-sigle">' + escapeHtml(sigle) + "</span>" +
        '<span class="party-name">' + escapeHtml(cfg.name) + "</span>";
      btn.addEventListener("click", () => handleGuess(sigle));

      els.partyGrid.appendChild(btn);
    });
  }

  function handleGuess(guessedSigle) {
    if (answered) return;
    answered = true;
    total++;

    const pol = pool[currentIndex];
    const isCorrect = guessedSigle === pol.groupe_sigle;

    if (isCorrect) {
      score++;
      streak++;
      if (streak > bestStreak) {
        bestStreak = streak;
        localStorage.setItem("polidle-best", String(bestStreak));
      }
    } else {
      streak = 0;
    }

    // Update button visuals
    els.partyGrid.querySelectorAll(".party-btn").forEach((btn) => {
      const sigle = btn.querySelector(".party-sigle").textContent;
      if (sigle === pol.groupe_sigle) {
        btn.classList.add("correct");
      } else if (sigle === guessedSigle && !isCorrect) {
        btn.classList.add("wrong");
      } else {
        btn.classList.add("dimmed");
      }
      btn.disabled = true;
    });

    // Reveal answer
    const cfg = getPartyConfig(pol.groupe_sigle);
    els.revealIcon.textContent = isCorrect ? "✅" : "❌";
    els.revealName.textContent = pol.nom_complet;
    els.revealGroup.textContent = cfg.name + " (" + pol.groupe_sigle + ")";
    els.answerReveal.classList.remove("hidden", "correct-reveal", "wrong-reveal");
    els.answerReveal.classList.add(isCorrect ? "correct-reveal" : "wrong-reveal");

    // Show next
    els.nextBtn.classList.remove("hidden");

    updateScoreDisplay();
    currentIndex++;
  }

  // ----------------------------------------------------------
  // Score display
  // ----------------------------------------------------------
  function updateScoreDisplay() {
    els.score.textContent = score;
    els.total.textContent = total;
    els.streak.textContent = streak;
    els.bestStreak.textContent = bestStreak;
  }

  // ----------------------------------------------------------
  // Keyboard support
  // ----------------------------------------------------------
  function handleKeydown(e) {
    // Enter or Space → next
    if (answered && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      nextPolitician();
      return;
    }

    // Number keys → select party
    if (!answered && e.key >= "1" && e.key <= "9") {
      const idx = parseInt(e.key, 10) - 1;
      if (idx < parties.length) {
        handleGuess(parties[idx]);
      }
    }
  }

  // ----------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------
  function getPartyConfig(sigle) {
    if (PARTY_COLORS[sigle]) {
      return PARTY_COLORS[sigle];
    }
    // Try to find a name from the data itself
    const found = pool.find((p) => p.groupe_sigle === sigle);
    const name = (found && found.groupe_nom) ? found.groupe_nom : sigle;
    return { name, color: autoColor(sigle) };
  }

  function autoColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash % 360);
    return "hsl(" + hue + ", 55%, 45%)";
  }

  function shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // ----------------------------------------------------------
  // Boot
  // ----------------------------------------------------------
  document.addEventListener("DOMContentLoaded", init);
})();
