const fields = {
  account: document.querySelector("#account"),
  destination: document.querySelector("#destination"),
  weekday: document.querySelector("#weekday"),
  time: document.querySelector("#time"),
  retention: document.querySelector("#retention"),
  repos: document.querySelector("#repos"),
  repoCount: document.querySelector("#repoCount"),
  schedule: document.querySelector("#schedule"),
  keep: document.querySelector("#keep"),
  output: document.querySelector("#output"),
  manifest: document.querySelector("#manifest"),
};

function repositories() {
  return fields.repos.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function buildManifest() {
  const repos = repositories();
  return {
    backup_version: 1,
    created_at: new Date().toISOString(),
    github_user: fields.account.value.trim() || "unknown",
    backup_destination: fields.destination.value.trim(),
    schedule: `${fields.weekday.value} at ${fields.time.value}`,
    retention: Number(fields.retention.value),
    repositories_found: repos.length,
    repositories_successful: repos.length,
    repositories_failed: 0,
    repositories: repos.map((nameWithOwner) => {
      const name = nameWithOwner.split("/").pop();
      return {
        name,
        name_with_owner: nameWithOwner,
        branch: "main or default branch",
        status: "planned",
        archive: `${nameWithOwner.replace("/", "__")}.zip`,
      };
    }),
  };
}

function update() {
  const manifest = buildManifest();
  fields.repoCount.textContent = String(manifest.repositories_found);
  fields.schedule.textContent = manifest.schedule;
  fields.keep.textContent = `${manifest.retention} backups`;
  fields.output.textContent = `${manifest.repositories_found} ZIP files + manifest`;
  fields.manifest.textContent = JSON.stringify(manifest, null, 2);
}

function downloadManifest() {
  const blob = new Blob([JSON.stringify(buildManifest(), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "backup_manifest_sample.json";
  link.click();
  URL.revokeObjectURL(url);
}

document.querySelector("#planButton").addEventListener("click", update);
document.querySelector("#downloadManifest").addEventListener("click", downloadManifest);
Object.values(fields).forEach((field) => {
  if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement) {
    field.addEventListener("input", update);
  }
});
update();

