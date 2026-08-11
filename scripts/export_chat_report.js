"use strict";

const {Document, HeadingLevel, Packer, Paragraph, TextRun} = require("docx");

function textParagraph(text, options = {}) {
    return new Paragraph({
        ...options,
        children: [new TextRun({text: String(text || ""), font: "Arial Unicode MS", size: 21})],
        spacing: {after: 120, line: 300},
    });
}

async function main() {
    const chunks = [];
    for await (const chunk of process.stdin) chunks.push(chunk);
    const report = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    const children = [
        new Paragraph({text: report.title, heading: HeadingLevel.TITLE, spacing: {after: 220}}),
        textParagraph("FROGENT Agent report"),
        textParagraph(`Conversation: ${report.id}`),
        textParagraph(`Created: ${report.created_at}`),
        textParagraph(`Updated: ${report.updated_at}`),
        new Paragraph({text: "Conversation", heading: HeadingLevel.HEADING_1}),
    ];
    for (const item of report.messages) {
        children.push(new Paragraph({text: item.role, heading: HeadingLevel.HEADING_2}));
        for (const line of String(item.content || "(empty)").split("\n")) {
            children.push(textParagraph(line || " "));
        }
        if (item.attachments.length) children.push(textParagraph(`Attachments: ${item.attachments.join(", ")}`));
    }
    if (report.structures.length) {
        children.push(new Paragraph({text: "Molecular structures", heading: HeadingLevel.HEADING_1}));
        for (const item of report.structures) {
            children.push(textParagraph(`${item.filename} (${item.format || "unknown"})`, {bullet: {level: 0}}));
        }
    }
    const document = new Document({
        creator: "FROGENT Agent",
        title: report.title,
        description: "Exported FROGENT Agent report",
        sections: [{properties: {}, children}],
    });
    process.stdout.write(await Packer.toBuffer(document));
}

main().catch((error) => {
    process.stderr.write(String(error && error.stack || error));
    process.exitCode = 1;
});
