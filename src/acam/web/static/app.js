(() => {
  "use strict";

  // Drag-and-drop upload zone: show the chosen file names.
  const zone = document.getElementById("dropzone");
  const input = document.getElementById("file-input");
  const list = document.getElementById("dz-files");
  if (zone && input) {
    const show = () => {
      const names = Array.from(input.files).map((f) => f.name);
      list.textContent = names.length ? names.join(", ") : "";
    };
    input.addEventListener("change", show);
    ["dragenter", "dragover"].forEach((ev) =>
      zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("drag"); }));
    ["dragleave", "drop"].forEach((ev) =>
      zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("drag"); }));
    zone.addEventListener("drop", (e) => {
      if (e.dataTransfer && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        show();
      }
    });
  }

  // Client-side filtering of the sources table.
  const table = document.getElementById("sources-table");
  if (table) {
    const text = document.getElementById("filter-text");
    const status = document.getElementById("filter-status");
    const tag = document.getElementById("filter-tag");
    const apply = () => {
      const q = (text && text.value.trim().toLowerCase()) || "";
      const st = (status && status.value) || "";
      const tg = (tag && tag.value) || "";
      table.querySelectorAll("tbody tr").forEach((row) => {
        const ok = (!q || row.dataset.search.includes(q)) &&
          (!st || row.dataset.status === st) &&
          (!tg || row.dataset.tags.split(",").includes(tg));
        row.hidden = !ok;
      });
    };
    [text, status, tag].forEach((el) => el && el.addEventListener("input", apply));

    const all = document.getElementById("select-all");
    if (all) {
      all.addEventListener("change", () => {
        table.querySelectorAll("tbody tr:not([hidden]) input[name=source]")
          .forEach((cb) => { cb.checked = all.checked; });
      });
    }
  }

  // Poll background analysis jobs; reload once the active ones finish.
  const poller = document.querySelector("[data-poll]");
  if (poller) {
    const url = poller.dataset.poll;
    const activeCount = (jobs) => jobs.filter((j) => j.state === "queued" || j.state === "running").length;
    // Active job count when the page was rendered.
    let previous = poller.dataset.active ? Number(poller.dataset.active) : null;
    const tick = async () => {
      try {
        const res = await fetch(url, { headers: { Accept: "application/json" } });
        const jobs = await res.json();
        const active = activeCount(jobs);
        if (previous !== null && active < previous) { window.location.reload(); return; }
        previous = active;
        if (active > 0) setTimeout(tick, 2500);
      } catch (_) {
        setTimeout(tick, 5000);
      }
    };
    tick();
  }

  // Copy-to-clipboard buttons.
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const target = document.querySelector(btn.dataset.copy);
      if (!target) return;
      const text = Array.from(target.querySelectorAll(".reference")).map((p) => p.innerText).join("\n\n");
      try {
        await navigator.clipboard.writeText(text);
        const label = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => { btn.textContent = label; }, 1500);
      } catch (_) { /* clipboard unavailable */ }
    });
  });
})();
