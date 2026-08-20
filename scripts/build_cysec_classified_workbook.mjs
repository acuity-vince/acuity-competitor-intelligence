import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputCsv, outputXlsx, activeCsv, previewDir] = process.argv.slice(2);
const csvText = await fs.readFile(inputCsv, "utf8");
const imported = await Workbook.fromCSV(csvText, { sheetName: "All CySEC Records" });
const raw = imported.worksheets.getItem("All CySEC Records");
const values = raw.getUsedRange(true).values;
const headers = values[0].map((value, index) => index === 0 ? String(value).replace(/^\uFEFF/, "") : String(value));
const rows = values.slice(1);
const statusIndex = headers.indexOf("status");
const brokerIndex = headers.indexOf("forex_broker");
const confidenceIndex = headers.indexOf("classification_confidence");
const reviewIndex = headers.indexOf("needs_review");

const activeRows = rows
  .filter((row) => row[statusIndex] === "ACTIVE")
  .sort((a, b) =>
    String(b[brokerIndex]).localeCompare(String(a[brokerIndex])) ||
    String(a[reviewIndex]).localeCompare(String(b[reviewIndex])) ||
    String(a[0]).localeCompare(String(b[0])),
  );
const inactiveRows = rows
  .filter((row) => row[statusIndex] !== "ACTIVE")
  .sort((a, b) => String(a[statusIndex]).localeCompare(String(b[statusIndex])) || String(a[0]).localeCompare(String(b[0])));

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const active = workbook.worksheets.add("Active Firms");
const inactive = workbook.worksheets.add("Inactive Audit");

const activeYes = activeRows.filter((row) => row[brokerIndex] === "YES").length;
const activeNo = activeRows.filter((row) => row[brokerIndex] === "NO").length;
const activeReview = activeRows.filter((row) => row[reviewIndex] === "YES").length;
summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["CySEC Active Firm Classification"]];
summary.getRange("A2:F2").merge();
summary.getRange("A2").values = [["Operational prospect view — evidence checked against CySEC-approved domains"]];
summary.getRange("A4:B8").values = [
  ["Metric", "Count"],
  ["Active licence records", activeRows.length],
  ["Forex / CFD / prop: YES", activeYes],
  ["Forex / CFD / prop: NO", activeNo],
  ["Needs manual review", activeReview],
];
summary.getRange("D4:F8").values = [
  ["How to use", "Meaning", "Action"],
  ["YES / HIGH", "Strong product evidence", "Include in prospect list"],
  ["YES / LOW", "Possible target", "Verify before outreach"],
  ["NO / HIGH", "Clear non-target", "Exclude"],
  ["NO / LOW", "No affirmative evidence", "Review before permanent exclusion"],
];
summary.getRange("A10:F11").merge(true);
summary.getRange("A10").values = [["Scope note"]];
summary.getRange("A11").values = [["Only ACTIVE CySEC records appear in the working sheet. Cancelled, formerly authorised, and surrender-pending records are retained separately for audit history."]];

active.getRangeByIndexes(0, 0, activeRows.length + 1, headers.length).values = [headers, ...activeRows];
inactive.getRangeByIndexes(0, 0, inactiveRows.length + 1, headers.length).values = [headers, ...inactiveRows];

const navy = "#123B5D";
const blue = "#1677B8";
const paleBlue = "#EAF4FA";
const paleGreen = "#E8F5E9";
const paleRed = "#FDECEC";
const paleAmber = "#FFF4D6";
summary.showGridLines = false;
summary.getRange("A1:F1").format = { fill: navy, font: { color: "#FFFFFF", bold: true, size: 18 }, rowHeight: 32, verticalAlignment: "center" };
summary.getRange("A2:F2").format = { fill: paleBlue, font: { color: navy, italic: true }, rowHeight: 24 };
summary.getRange("A4:B4").format = { fill: blue, font: { color: "#FFFFFF", bold: true } };
summary.getRange("D4:F4").format = { fill: blue, font: { color: "#FFFFFF", bold: true } };
summary.getRange("A4:B8").format.borders = { preset: "all", style: "thin", color: "#D5E1E8" };
summary.getRange("D4:F8").format.borders = { preset: "all", style: "thin", color: "#D5E1E8" };
summary.getRange("A10:F10").format = { fill: navy, font: { color: "#FFFFFF", bold: true } };
summary.getRange("A11:F11").format = { fill: paleBlue, wrapText: true, rowHeight: 42 };
summary.getRange("A:F").format.columnWidth = 22;
summary.getRange("D:D").format.columnWidth = 18;
summary.getRange("E:F").format.columnWidth = 28;

for (const [sheet, dataRows] of [[active, activeRows], [inactive, inactiveRows]]) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
  const lastRow = dataRows.length + 1;
  const lastCol = String.fromCharCode(64 + headers.length);
  sheet.getRange(`A1:${lastCol}1`).format = { fill: navy, font: { color: "#FFFFFF", bold: true }, wrapText: true, rowHeight: 34 };
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.borders = { preset: "inside", style: "thin", color: "#E6EDF2" };
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.font = { size: 9 };
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.wrapText = false;
  sheet.getRange("A:A").format.columnWidth = 36;
  sheet.getRange("B:O").format.columnWidth = 16;
  sheet.getRange(`N2:O${lastRow}`).setNumberFormat("yyyy-mm-dd hh:mm");
  sheet.getRange("P:P").format.columnWidth = 11;
  sheet.getRange("Q:Q").format.columnWidth = 14;
  sheet.getRange("R:R").format.columnWidth = 46;
  sheet.getRange("S:S").format.columnWidth = 32;
  sheet.getRange("T:U").format.columnWidth = 14;
  sheet.getRange(`P2:P${lastRow}`).conditionalFormats.add("cellValue", { operator: "equalTo", formula: '"YES"', format: { fill: paleGreen, font: { color: "#176A39", bold: true } } });
  sheet.getRange(`P2:P${lastRow}`).conditionalFormats.add("cellValue", { operator: "equalTo", formula: '"NO"', format: { fill: paleRed, font: { color: "#8D2C2C" } } });
  sheet.getRange(`U2:U${lastRow}`).conditionalFormats.add("cellValue", { operator: "equalTo", formula: '"YES"', format: { fill: paleAmber, font: { color: "#7A5700", bold: true } } });
  sheet.tables.add(`A1:${lastCol}${lastRow}`, true, `${sheet.name.replace(/\s/g, "")}Table`);
}

const escapeCsv = (value) => {
  const text = value == null ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
await fs.writeFile(activeCsv, [headers, ...activeRows].map((row) => row.map(escapeCsv).join(",")).join("\r\n"), "utf8");
const out = await SpreadsheetFile.exportXlsx(workbook);
await out.save(outputXlsx);
await fs.mkdir(previewDir, { recursive: true });
for (const sheetName of ["Summary", "Active Firms"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${previewDir}/${sheetName.replace(/\s/g, "-").toLowerCase()}.png`, new Uint8Array(await preview.arrayBuffer()));
}
console.log((await workbook.inspect({ kind: "sheet,table", maxChars: 4000, tableMaxRows: 3, tableMaxCols: 8 })).ndjson);
console.log((await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 20 }, maxChars: 2000 })).ndjson);
console.log(JSON.stringify({ activeRows: activeRows.length, activeYes, activeNo, activeReview, inactiveRows: inactiveRows.length }));
