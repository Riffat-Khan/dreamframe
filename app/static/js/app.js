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

        function withCacheBust(url, token) {
            if (!url) return url;
            return url.includes("?") ? url : `${url}?v=${token}`;
        }

        function loadImageWithRetry(media, panelNumber, imageUrl, caption) {
            const status = media?.querySelector(".panel-status");
            const delays = [4000, 8000, 16000, 20000, 20000]; // free API is rate-limited; back off between retries

            return new Promise((resolve) => {
                let attempt = 0;

                const tryLoad = () => {
                    const img = new Image();
                    img.className = "panel-image";
                    img.alt = `Comic panel ${panelNumber}: ${caption}`;
                    img.onload = () => {
                        media.replaceChildren(img);
                        resolve(true);
                    };
                    img.onerror = () => {
                        if (attempt < delays.length) {
                            const wait = delays[attempt];
                            attempt += 1;
                            if (status) {
                                status.textContent = `Panel ${panelNumber} was rate-limited, retrying in ${wait / 1000}s…`;
                            }
                            setTimeout(tryLoad, wait);
                        } else {
                            resolve(false);
                        }
                    };
                    img.src = attempt === 0 ? imageUrl : withCacheBust(imageUrl, Date.now());
                };

                tryLoad();
            });
        }

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

        function showPanelPlaceholder(media, message) {
            const placeholder = document.createElement("div");
            placeholder.className = "panel-placeholder is-drawing";
            const status = document.createElement("p");
            status.className = "muted panel-scene-small panel-status";
            status.textContent = message;
            placeholder.appendChild(status);
            media.replaceChildren(placeholder);
        }

        async function runPanelJob(panelNumber, queueUrl) {
            const media = panelGrid.querySelector(`[data-panel-media="${panelNumber}"]`);
            if (!media) return;
            const placeholder = media.querySelector(".panel-placeholder");
            let status = media.querySelector(".panel-status");
            if (status) {
                status.textContent = `Drawing panel ${panelNumber}…`;
            }

            if (!dreamId) {
                if (status) status.textContent = "Could not determine dream ID.";
                placeholder?.classList.remove("is-drawing");
                return;
            }

            try {
                const queueResponse = await fetch(queueUrl, {
                    method: "POST",
                    headers: { Accept: "application/json" },
                });
                const queueData = await queueResponse.json();

                if (!queueData.ok) {
                    throw new Error(queueData.error || "Failed to queue image generation");
                }

                const caption = media.getAttribute("data-caption") || "";
                let imageUrl = queueData.image_url;

                if (queueData.status !== "completed") {
                    if (!queueData.task_id) {
                        throw new Error("No task ID returned");
                    }
                    const pollResult = await pollImageStatus(dreamId, panelNumber, queueData.task_id);
                    if (!pollResult.ok || !pollResult.image_url) {
                        status = media.querySelector(".panel-status");
                        if (status) status.textContent = pollResult.error || "Could not draw this panel. Try again.";
                        media.querySelector(".panel-placeholder")?.classList.remove("is-drawing");
                        return;
                    }
                    imageUrl = pollResult.image_url;
                }

                const loaded = await loadImageWithRetry(media, panelNumber, imageUrl, caption);
                if (!loaded) {
                    showPanelPlaceholder(media, "Could not draw this panel (rate limited). Try again.");
                }
            } catch (err) {
                showPanelPlaceholder(media, `Error: ${err.message || "Could not draw this panel."}`);
            }
        }

        function drawPanel(panelNumber) {
            return runPanelJob(panelNumber, `/dreams/${dreamId}/panels/${panelNumber}/image/generate`);
        }

        function regeneratePanel(panelNumber, button) {
            const media = panelGrid.querySelector(`[data-panel-media="${panelNumber}"]`);
            if (!media) return Promise.resolve();
            showPanelPlaceholder(media, `Redrawing panel ${panelNumber}…`);
            if (button) button.disabled = true;
            return runPanelJob(panelNumber, `/dreams/${dreamId}/panels/${panelNumber}/image/regenerate`).finally(() => {
                if (button) button.disabled = false;
            });
        }

        // Sequential, not Promise.all — the free image API rate-limits concurrent requests.
        (async () => {
            for (const panelNumber of pending) {
                await drawPanel(panelNumber);
            }
        })();

        panelGrid.querySelectorAll("[data-regenerate-panel]").forEach((button) => {
            button.addEventListener("click", () => {
                regeneratePanel(button.getAttribute("data-regenerate-panel"), button);
            });
        });

        // A panel that already rendered can still fail on a later page load
        // (free API hiccup) — retry it once automatically through the same path.
        panelGrid.querySelectorAll("img.panel-image").forEach((img) => {
            img.addEventListener(
                "error",
                () => {
                    const media = img.closest("[data-panel-media]");
                    const panelNumber = media?.getAttribute("data-panel-media");
                    if (panelNumber) regeneratePanel(panelNumber);
                },
                { once: true }
            );
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
