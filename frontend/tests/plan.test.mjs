import assert from "node:assert/strict";
import {parseItems, toMarkdown} from "../assets/plan.mjs";

assert.deepEqual(parseItems(" Python\npython\n\nJavaScript \r\n"), ["Python", "JavaScript"]);
const plan = {project_name: "Edited project", description: "Edited summary", languages: ["Python"],
  technologies: [], requirements: Array.from({length: 12}, (_, i) => `Task ${i}`), components: ["API"], deliverables: ["Report"]};
const markdown = toMarkdown(plan, "brief.pdf");
assert.ok(markdown.includes("# Edited project"));
assert.ok(markdown.includes("Source brief: brief.pdf"));
assert.ok(markdown.includes("## Technologies\n\nNone specified."));
assert.ok(markdown.includes("- Task 11"));
assert.ok(markdown.includes("## Deliverables\n\n- Report"));
console.log("PASS: edited Markdown export, deduplication, empty categories, and unlimited merged items");
