import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";

const artifactToolRoot = process.env.ARTIFACT_TOOL_ROOT;
if (!artifactToolRoot) {
  throw new Error("ARTIFACT_TOOL_ROOT must point to the bundled @oai/artifact-tool package");
}
const { SpreadsheetFile, Workbook } = await import(
  pathToFileURL(`${artifactToolRoot}/dist/artifact_tool.mjs`).href
);

const [inputCsv, outputXlsx, previewDir] = process.argv.slice(2);
const imported = await Workbook.fromCSV(await fs.readFile(inputCsv, "utf8"), { sheetName: "Active Master" });
const source = imported.worksheets.getItem("Active Master");
const values = source.getUsedRange(true).values;
const headers = values[0].map((value, index) => index === 0 ? String(value).replace(/^\uFEFF/, "") : String(value));
const rows = values.slice(1);
const regulatorIndex = headers.indexOf("regulator_code");
const brokerIndex = headers.indexOf("forex_broker");
const reviewIndex = headers.indexOf("needs_review");

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const master = workbook.worksheets.add("Active Master");
const review = workbook.worksheets.add("Review Queue");
const reviewRows = rows.filter((row) => row[reviewIndex] === "YES");
master.getRangeByIndexes(0, 0, rows.length + 1, headers.length).values = [headers, ...rows];
review.getRangeByIndexes(0, 0, reviewRows.length + 1, headers.length).values = [headers, ...reviewRows];

const regulatorCodes = [...new Set(rows.map((row) => String(row[regulatorIndex])))].sort();
const metrics = [["Regulator", "Active records", "Forex target: YES", "Clear non-target", "Needs review"]];
for (const code of regulatorCodes) {
  const subset = rows.filter((row) => row[regulatorIndex] === code);
  metrics.push([
    code,
    subset.length,
    subset.filter((row) => row[brokerIndex] === "YES").length,
    subset.filter((row) => row[brokerIndex] === "NO" && row[reviewIndex] === "NO").length,
    subset.filter((row) => row[reviewIndex] === "YES").length,
  ]);
}
summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["Acuity Forex Broker Master Registry"]];
summary.getRange("A2:F2").merge();
summary.getRange("A2").values = [["Active regulator records normalized for sales intelligence"]];
summary.getRangeByIndexes(3, 0, metrics.length, metrics[0].length).values = metrics;
summary.getRange("A9:F9").merge();
summary.getRange("A9").values = [["Classification note"]];
summary.getRange("A10:F11").merge(true);
summary.getRange("A10").values = [["CySEC classifications use approved-domain evidence. ASIC classifications use official AFS licence authorisations. FCA rows are active legal-entity matches verified through the official Register API; ambiguous group-name matches are excluded."]];
summary.getRange("A11").values = [["Only active licence records are included in this master workbook. Use regulator_code to filter CySEC, ASIC, FSCA, FCA, or FSC Mauritius as additional baselines are added."]];

const navy = "#123B5D", blue = "#1677B8", paleBlue = "#EAF4FA", green = "#E8F5E9", red = "#FDECEC", amber = "#FFF4D6";
summary.showGridLines = false;
summary.getRange("A1:F1").format = { fill: navy, font: { color: "#FFFFFF", bold: true, size: 18 }, rowHeight: 32 };
summary.getRange("A2:F2").format = { fill: paleBlue, font: { color: navy, italic: true }, rowHeight: 24 };
summary.getRange(`A4:E${3 + metrics.length}`).format.borders = { preset: "all", style: "thin", color: "#D5E1E8" };
summary.getRange("A4:E4").format = { fill: blue, font: { color: "#FFFFFF", bold: true } };
summary.getRange("A9:F9").format = { fill: navy, font: { color: "#FFFFFF", bold: true } };
summary.getRange("A10:F11").format = { fill: paleBlue, wrapText: true, rowHeight: 34 };
summary.getRange("A:F").format.columnWidth = 23;

for (const [sheet, dataRows, tableName] of [[master, rows, "ActiveMasterTable"], [review, reviewRows, "ReviewQueueTable"]]) {
  const lastRow = dataRows.length + 1;
  const lastCol = "Q";
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(2);
  sheet.getRange(`A1:${lastCol}1`).format = { fill: navy, font: { color: "#FFFFFF", bold: true, size: 9 }, wrapText: true, rowHeight: 34 };
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.font = { size: 9 };
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.borders = { preset: "inside", style: "thin", color: "#E6EDF2" };
  sheet.getRange("A:A").format.columnWidth = 34;
  sheet.getRange("B:B").format.columnWidth = 12;
  sheet.getRange("C:Q").format.columnWidth = 17;
  sheet.getRange("L:L").format.columnWidth = 48;
  sheet.getRange("M:M").format.columnWidth = 32;
  sheet.getRange(`J2:J${lastRow}`).conditionalFormats.add("cellValue", { operator: "equalTo", formula: '"YES"', format: { fill: green, font: { color: "#176A39", bold: true } } });
  sheet.getRange(`J2:J${lastRow}`).conditionalFormats.add("cellValue", { operator: "equalTo", formula: '"NO"', format: { fill: red, font: { color: "#8D2C2C" } } });
  sheet.getRange(`O2:O${lastRow}`).conditionalFormats.add("cellValue", { operator: "equalTo", formula: '"YES"', format: { fill: amber, font: { color: "#7A5700", bold: true } } });
  sheet.tables.add(`A1:${lastCol}${lastRow}`, true, tableName);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputXlsx);
await fs.mkdir(previewDir, { recursive: true });
for (const sheetName of ["Summary", "Active Master"]) {
  const image = await workbook.render({ sheetName, range: sheetName === "Active Master" ? "A1:Q35" : "A1:F11", autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${previewDir}/${sheetName.replace(/\s/g, "-").toLowerCase()}.png`, new Uint8Array(await image.arrayBuffer()));
}
console.log((await workbook.inspect({ kind: "sheet,table", maxChars: 3500, tableMaxRows: 3, tableMaxCols: 7 })).ndjson);
console.log((await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 20 }, maxChars: 1200 })).ndjson);
console.log(JSON.stringify({ rows: rows.length, reviewRows: reviewRows.length, regulators: regulatorCodes }));
