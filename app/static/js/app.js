(() => {
  const overlay = document.getElementById("loading-overlay");
  const messageEl = document.getElementById("loading-message");
  if (!overlay || !messageEl) return;

  function showLoading(message) {
    messageEl.textContent = message || "Working on your dream…";
    overlay.hidden = false;
    document.body.classList.add("is-loading");
  }

  document.querySelectorAll("form[data-loading]").forEach((form) => {
    form.addEventListener("submit", () => {
      // Respect delete confirm / invalid HTML5 validation
      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }
      const reanalyze = form.querySelector('input[name="reanalyze"]');
      let message = form.getAttribute("data-loading") || "Working on your dream…";
      if (reanalyze && !reanalyze.checked) {
        message = "Saving your dream…";
      } else if (reanalyze && reanalyze.checked) {
        message = "Saving and rewriting your comic…";
      }
      showLoading(message);

      form.querySelectorAll("button[type='submit'], button:not([type])").forEach((btn) => {
        btn.disabled = true;
      });
    });
  });

  const panelGrid = document.querySelector("[data-draw-panels]");
  if (panelGrid) {
    const pending = (panelGrid.getAttribute("data-pending-panels") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const urlTemplate = panelGrid.getAttribute("data-draw-url") || "";

    async function drawPanel(panelNumber) {
      const media = panelGrid.querySelector(`[data-panel-media="${panelNumber}"]`);
      const placeholder = media?.querySelector(".panel-placeholder");
      const status = media?.querySelector(".panel-status");
      if (placeholder) {
        placeholder.classList.add("is-drawing");
      }
      if (status) {
        status.textContent = `Drawing panel ${panelNumber}…`;
      }
      const url = urlTemplate.replace("/panels/999/", `/panels/${panelNumber}/`);
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const data = await response.json();
        if (data.ok && data.image_url && media) {
          const caption = media.getAttribute("data-caption") || "";
          const img = document.createElement("img");
          img.className = "panel-image";
          img.alt = `Comic panel ${panelNumber}: ${caption}`;
          img.src = `${data.image_url}?v=${Date.now()}`;
          media.replaceChildren(img);
        } else if (status) {
          status.textContent = data.error || "Could not draw this panel. Try Regenerate images.";
          placeholder?.classList.remove("is-drawing");
        }
      } catch (_) {
        if (status) {
          status.textContent = "Could not draw this panel. Try Regenerate images.";
        }
        placeholder?.classList.remove("is-drawing");
      }
    }

    Promise.allSettled(
      pending.map((panelNumber) => drawPanel(panelNumber))
        ).then((results) => {
            console.log("All panel generation requests completed:", results);
        });
  }

  // Postcard PNG export (client-side canvas from the postcard card)
  const postcard = document.getElementById("dream-postcard");
  const pngBtn = document.getElementById("download-png");
  if (postcard && pngBtn) {
    pngBtn.addEventListener("click", async () => {
      try {
        const canvas = document.createElement("canvas");
        const width = 1080;
        const height = 620;
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const gradient = ctx.createLinearGradient(0, 0, width, height);
        gradient.addColorStop(0, "#0f1220");
        gradient.addColorStop(0.55, "#171b2e");
        gradient.addColorStop(1, "#1a1430");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);

        const brand = postcard.querySelector(".postcard-brand")?.textContent || "Dreamframe";
        const title = postcard.querySelector("h2")?.textContent || "Dream";
        const line = postcard.querySelector(".postcard-line")?.textContent || "";

        ctx.fillStyle = "#f0a6ca";
        ctx.font = "600 18px Outfit, Arial";
        ctx.fillText(brand.toUpperCase(), 48, 56);

        ctx.fillStyle = "#f4f1ea";
        ctx.font = "700 36px Georgia, serif";
        ctx.fillText(title.slice(0, 42), 48, 104);

        ctx.fillStyle = "#b7b3c8";
        ctx.font = "16px Outfit, Arial";
        ctx.fillText(line.slice(0, 90), 48, 136);

        const images = [...postcard.querySelectorAll(".postcard-panel-frame img")];
        const panelWidth = 276;
        const gap = 24;
        const startX = 48;
        const top = 170;

        for (let i = 0; i < Math.min(images.length, 3); i += 1) {
          const img = images[i];
          const x = startX + i * (panelWidth + gap);
          try {
            await img.decode?.();
            ctx.drawImage(img, x, top, panelWidth, panelWidth);
          } catch (_) {
            ctx.fillStyle = "#1a2033";
            ctx.fillRect(x, top, panelWidth, panelWidth);
          }
          const caption = img.closest(".postcard-panel")?.querySelector("figcaption")?.textContent || "";
          ctx.fillStyle = "#f4f1ea";
          ctx.font = "16px Georgia, serif";
          ctx.fillText(caption.slice(0, 34), x, top + panelWidth + 28);
        }

        ctx.fillStyle = "#7dd3c7";
        ctx.font = "14px Georgia, serif";
        ctx.fillText("Dreamframe — for reflection and fun, not therapy.", 48, 580);

        const link = document.createElement("a");
        link.download = "dreamframe-postcard.png";
        link.href = canvas.toDataURL("image/png");
        link.click();
      } catch (err) {
        console.error(err);
        window.print();
      }
    });
  }
})();
