export const listFields = ["languages", "technologies", "requirements", "components", "deliverables"];

export function parseItems(text) {
  const seen = new Set();
  return text.split(/\r?\n/).map(line => line.trim()).filter(item => {
    const key = item.toLowerCase();
    if (!item || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function toMarkdown(analysis, filename = "") {
  const parts = [`# ${analysis.project_name || "Project build plan"}`, analysis.description || ""];
  if (filename) parts.push(`Source brief: ${filename}`);
  for (const field of listFields) {
    parts.push(`## ${field[0].toUpperCase() + field.slice(1)}`);
    parts.push(analysis[field].length ? analysis[field].map(item => `- ${item}`).join("\n") : "None specified.");
  }
  return parts.join("\n\n") + "\n";
}
