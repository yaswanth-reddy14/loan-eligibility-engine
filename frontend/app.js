"use strict";
let apiToken = "",
  selectedFile = null,
  currentJobId = "",
  initializedJob = false;
const el = (id) => document.getElementById(id);
const showError = (error) => {
  el("error").textContent = error.message || String(error);
  el("error").hidden = false;
};
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${apiToken}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const data = await response.json();
    throw Error(
      data.detail ? JSON.stringify(data.detail) : `HTTP ${response.status}`,
    );
  }
  return response.json();
}
function cell(row, value) {
  const td = document.createElement("td");
  td.textContent = value ?? "—";
  row.append(td);
}
function card(parent, value, label) {
  const div = document.createElement("div");
  div.className = "card";
  const strong = document.createElement("strong");
  strong.textContent = value;
  const span = document.createElement("span");
  span.textContent = label;
  div.append(strong, span);
  parent.append(div);
}
async function refresh() {
  if (!apiToken) return;
  try {
    const data = await api(
      "/api/dashboard" +
        (currentJobId ? "?job_id=" + encodeURIComponent(currentJobId) : ""),
    );
    if (!initializedJob) {
      initializedJob = true;
      if (data.available_jobs.length) {
        currentJobId = data.available_jobs[0].id;
        return refresh();
      }
    }
    el("mode").textContent =
      `${data.demo_mode || data.email_delivery_mode === "preview" ? "DEMO MODE" : "TEST MODE"} / ${data.email_delivery_mode === "preview" ? "MAILPIT PREVIEW" : "SES TEST"}`;
    el("counts").replaceChildren();
    card(
      el("counts"),
      data.jobs.reduce((sum, j) => sum + j.accepted, 0),
      "Accepted in shown jobs",
    );
    card(el("counts"), data.products.length, "Loaded products");
    card(
      el("counts"),
      data.matches.POSSIBLY_ELIGIBLE || 0,
      "Possibly eligible outcomes",
    );
    card(
      el("counts"),
      data.matches.REVIEW_REQUIRED || 0,
      "Review outcomes (no email)",
    );
    card(
      el("counts"),
      data.notifications.SENT || 0,
      data.email_delivery_mode === "preview"
        ? "Mailpit messages sent"
        : "SES test messages sent",
    );
    el("job-filter").replaceChildren(
      new Option("All jobs (latest 20 shown)", ""),
      ...data.available_jobs.map(
        (j) => new Option(`${j.id} / ${j.status}`, j.id),
      ),
    );
    el("job-filter").value = currentJobId;
    el("discovery-runs").replaceChildren();
    for (const run of data.discovery_runs) {
      const p = document.createElement("p");
      p.textContent = `${run.status}: ${run.source_url} / ${run.detail}`;
      el("discovery-runs").append(p);
    }
    el("jobs").replaceChildren();
    for (const job of data.jobs) {
      const row = document.createElement("tr");
      [
        job.id,
        job.status,
        job.accepted,
        job.rejected,
        job.error_summary,
      ].forEach((v) => cell(row, v));
      el("jobs").append(row);
    }
    el("products").replaceChildren();
    for (const product of data.products) {
      const div = document.createElement("div");
      div.className = "product";
      const title = document.createElement("h3");
      title.textContent = product.lender;
      const details = document.createElement("p");
      details.textContent = `${product.product_name} · ${product.verification_status} · ${product.rate_representation}`;
      const link = document.createElement("a");
      link.textContent = "Source evidence";
      link.href = product.source_url;
      link.rel = "noopener noreferrer";
      link.target = "_blank";
      div.append(title, details, link);
      el("products").append(div);
    }
    el("workflows").replaceChildren();
    for (const run of data.workflows) {
      const div = document.createElement("div");
      div.className = "run";
      const title = document.createElement("strong");
      title.textContent = `Workflow ${run.workflow} · ${run.status} · ${run.job_id}`;
      const metrics = document.createElement("pre");
      metrics.textContent = JSON.stringify(run.metrics, null, 2);
      div.append(title, metrics);
      el("workflows").append(div);
    }
  } catch (error) {
    showError(error);
  }
}
function choose(file) {
  selectedFile = file;
  el("upload").disabled = true;
  if (!file) return;
  if (
    !file.name.toLowerCase().endsWith(".csv") ||
    file.size > 20 * 1024 * 1024 ||
    !file.size
  ) {
    showError(Error("Select a nonempty CSV up to 20 MB."));
    return;
  }
  file
    .slice(0, 2048)
    .text()
    .then((text) => {
      const first = text.replace(/^\uFEFF/, "").split(/\r?\n/)[0];
      const expected =
        "user_id,name,email,monthly_income,credit_score,employment_status,age";
      el("preview").textContent =
        `${file.name} · ${file.size.toLocaleString()} bytes\n${first}\nFull row validation runs in the ingestion worker.`;
      if (first !== expected) {
        showError(Error("CSV headers do not match the required schema."));
        return;
      }
      el("error").hidden = true;
      el("upload").disabled = false;
    });
}
el("file").addEventListener("change", (e) => choose(e.target.files[0]));
el("drop").addEventListener("dragover", (e) => e.preventDefault());
el("drop").addEventListener("drop", (e) => {
  e.preventDefault();
  choose(e.dataTransfer.files[0]);
});
el("connect").addEventListener("click", () => {
  apiToken = el("token").value;
  el("token").value = "";
  el("error").hidden = true;
  refresh();
});
el("upload").addEventListener("click", async () => {
  if (!selectedFile || !apiToken) {
    showError(Error("Connect with the local API token first."));
    return;
  }
  el("upload").disabled = true;
  try {
    el("upload-status").textContent = "Calculating checksum…";
    const bytes = await selectedFile.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const checksum = Array.from(new Uint8Array(digest), (n) =>
      n.toString(16).padStart(2, "0"),
    ).join("");
    const init = await api("/api/uploads", {
      method: "POST",
      body: JSON.stringify({
        filename: selectedFile.name,
        size: selectedFile.size,
        checksum,
      }),
    });
    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", init.url);
      Object.entries(init.headers).forEach(([k, v]) =>
        xhr.setRequestHeader(k, v),
      );
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable)
          el("progress").value = (100 * e.loaded) / e.total;
      };
      xhr.onload = () =>
        xhr.status < 300
          ? resolve()
          : reject(Error(`Object upload failed: ${xhr.status}`));
      xhr.onerror = () => reject(Error("Object storage connection failed"));
      xhr.send(selectedFile);
    });
    currentJobId = init.job_id;
    const result = await api(`/api/uploads/${init.job_id}/complete`, {
      method: "POST",
    });
    el("upload-status").textContent = `Job ${init.job_id}: ${result.status}`;
    await refresh();
  } catch (error) {
    showError(error);
  } finally {
    el("upload").disabled = false;
  }
});
setInterval(refresh, 5000);

el("job-filter").addEventListener("change", (e) => {
  currentJobId = e.target.value;
  refresh();
});
el("discover").addEventListener("click", async () => {
  try {
    el("discover").disabled = true;
    await api("/api/discovery/demo", { method: "POST" });
    el("discovery-status").textContent =
      "n8n A accepted. Confirm three new FIXTURE audit records and the execution in n8n.";
    await refresh();
  } catch (error) {
    showError(error);
  } finally {
    el("discover").disabled = false;
  }
});
