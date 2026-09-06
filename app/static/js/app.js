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
    const dreamId = panelGrid.getAttribute("data-dream-id") || "";

    async function pollImageStatus(dreamId, panelNumber, taskId) {
      /**
       * Poll for image generation status.
       * Returns: { ok: bool, image_url?: string, error?: string }
       */
      const media = panelGrid.querySelector(`[data-panel-media="${panelNumber}"]`);
      const placeholder = media?.querySelector(".panel-placeholder");
      const status = media?.querySelector(".panel-status");

      let attempts = 0;
      const maxAttempts = 180; // 30 minutes with 10s polling
      const pollInterval = 10000; // 10 seconds

      return new Promise((resolve) => {
        const poll = async () => {
          attempts += 1;
          const statusUrl = `/dreams/${dreamId}/panels/${panelNumber}/image/status/${taskId}`;
          try {
            const response = await fetch(statusUrl, {
              method: "GET",
              headers: { Accept: "application/json" },
            });
            const data = await response.json();

            if (!data.ok) {
              resolve({ ok: false, error: data.error || "Unknown error" });
              return;
            }

            if (data.status === "completed") {
              resolve({ ok: true, image_url: data.image_url });
            } else if (data.status === "failed") {
              resolve({ ok: false, error: data.error || "Image generation failed" });
            } else if (attempts >= maxAttempts) {
              resolve({ ok: false, error: "Image generation timed out after 30 minutes" });
            } else {
              // Still pending/running, poll again
              if (status) {
                status.textContent = `Drawing panel ${panelNumber}… (${Math.round((attempts * pollInterval) / 1000)}s)`;
              }
              setTimeout(poll, pollInterval);
            }
          } catch (err) {
            resolve({ ok: false, error: "Network error while checking status" });
          }
        };

        poll();
      });
    }

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

      if (!dreamId) {
        if (status) {
          status.textContent = "Could not determine dream ID.";
        }
        placeholder?.classList.remove("is-drawing");
        return;
      }

      try {
        // Step 1: Queue the image generation task
        const queueUrl = `/dreams/${dreamId}/panels/${panelNumber}/image/generate`;
        const queueResponse = await fetch(queueUrl, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const queueData = await queueResponse.json();

        if (!queueData.ok) {
          throw new Error(queueData.error || "Failed to queue image generation");
        }

        // If image already exists (task_id is null), use it immediately
        if (queueData.status === "completed") {
          const caption = media.getAttribute("data-caption") || "";
          const img = document.createElement("img");
          img.className = "panel-image";
          img.alt = `Comic panel ${panelNumber}: ${caption}`;
          img.src = `${queueData.image_url}?v=${Date.now()}`;
          media.replaceChildren(img);
          return;
        }

        const taskId = queueData.task_id;
        if (!taskId) {
          throw new Error("No task ID returned");
        }

        // Step 2: Poll for completion
        const pollResult = await pollImageStatus(dreamId, panelNumber, taskId);

        if (pollResult.ok && pollResult.image_url && media) {
          const caption = media.getAttribute("data-caption") || "";
          const img = document.createElement("img");
          img.className = "panel-image";
          img.alt = `Comic panel ${panelNumber}: ${caption}`;
          img.src = `${pollResult.image_url}?v=${Date.now()}`;
          media.replaceChildren(img);
        } else if (status) {
          status.textContent = pollResult.error || "Could not draw this panel. Try Regenerate images.";
          placeholder?.classList.remove("is-drawing");
        }
      } catch (err) {
        if (status) {
          status.textContent = `Error: ${err.message || "Could not draw this panel. Try Regenerate images."}`;
        }
        placeholder?.classList.remove("is-drawing");
      }
    }

    pending.forEach((panelNumber) => {
      drawPanel(panelNumber);
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
