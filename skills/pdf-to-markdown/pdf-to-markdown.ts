
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist/legacy/build/pdf.mjs";
import { join, basename, dirname } from "path";
import { writeFileSync, existsSync } from "fs";

// Configure worker
GlobalWorkerOptions.workerSrc = join(process.cwd(), "node_modules/pdfjs-dist/legacy/build/pdf.worker.mjs");

/**
 * Configuration for heuristics.
 * TUNABLES: Adjust these if layout detection fails.
 */
const CONFIG = {
    lineYTolerance: 2.0,       // Vertical drift allowed for items on the same line
    paraGapMultiplier: 1.5,    // Gap threshold relative to median gap for new paragraphs
    shortLineRatio: 0.85,      // Line width ratio < 0.85 indicates forced break (paragraph end)
    headerY: 810,              // Ignore content above this Y (header)
    footerY: 45,               // Ignore content below this Y (footer)
    pageNumYTop: 800,          // Header page number threshold
    pageNumYBottom: 60         // Footer page number threshold
};

interface TextItem {
    str: string;
    x: number;
    y: number;
    width: number;
    height: number;
    page: number;
}

interface VisualLine {
    text: string;
    y: number;
    minX: number;
    maxX: number;
    page: number;
}

async function main() {
    const args = process.argv.slice(2);
    if (args.length < 1) {
        console.error("Usage: bun .codebuddy/skills/pdf-to-markdown/pdf-to-markdown.ts <input.pdf> [password]");
        process.exit(1);
    }

    const inputPath = args[0];
    const password = args[1] || "";

    if (!existsSync(inputPath)) {
        die(`Input file not found: ${inputPath}`);
    }

    const outputPath = inputPath.replace(/\.pdf$/i, ".md");

    console.log(`Converting ${basename(inputPath)} -> ${basename(outputPath)}...`);

    try {
        const textItems = await extractPdfText(inputPath, password);
        const lines = groupTextIntoLines(textItems);
        const markdown = assembleMarkdown(lines);

        writeFileSync(outputPath, markdown);
        console.log(`Done. Wrote ${markdown.length} bytes.`);
    } catch (e: any) {
        die(`Conversion failed: ${e.message}`);
    }
}

/**
 * Core Logic Step 1: Extraction
 * Reads raw PDF objects, filtering out obvious artifacts (headers, footers).
 */
async function extractPdfText(path: string, password?: string): Promise<TextItem[]> {
    const items: TextItem[] = [];
    const loadingTask = getDocument({
        url: path,
        password: password,
        disableFontFace: true,
        standardFontDataUrl: join(process.cwd(), "node_modules/pdfjs-dist/standard_fonts/")
    });

    const pdf = await loadingTask.promise;

    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();

        for (const item of content.items as any[]) {
            if (!item.str || item.str.trim().length === 0) continue;

            const [ , , , , x, y ] = item.transform; // transform matrix [scaleX, skewY, skewX, scaleY, x, y]

            // Filter: Page margins (Header/Footer artifacts)
            if (y < CONFIG.footerY || y > CONFIG.headerY) continue;

            // Filter: Page numbers (heuristically detected at edges)
            const isDigit = /^\d{1,3}$/.test(item.str.trim());
            if (isDigit && (y < CONFIG.pageNumYBottom || y > CONFIG.pageNumYTop)) continue;

            items.push({
                str: item.str,
                x, y,
                width: item.width,
                height: item.height,
                page: i
            });
        }
    }
    return items;
}

/**
 * Core Logic Step 2: Line Assembly
 * Groups scattered text items into coherent visual lines based on Y-coordinates.
 * Solves the "split words" problem.
 */
function groupTextIntoLines(items: TextItem[]): VisualLine[] {
    // Sort: Page -> Y (desc) -> X (asc)
    items.sort((a, b) => {
        if (a.page !== b.page) return a.page - b.page;
        const yDiff = b.y - a.y;
        if (Math.abs(yDiff) > CONFIG.lineYTolerance) return yDiff;
        return a.x - b.x;
    });

    const lines: VisualLine[] = [];
    if (items.length === 0) return lines;

    let current: VisualLine = {
        text: items[0].str,
        y: items[0].y,
        minX: items[0].x,
        maxX: items[0].x + items[0].width,
        page: items[0].page
    };

    for (let i = 1; i < items.length; i++) {
        const item = items[i];

        // Check if item belongs to current line (Same page, Close Y)
        if (item.page === current.page && Math.abs(item.y - current.y) < CONFIG.lineYTolerance) {
            current.text += item.str;
            current.maxX = Math.max(current.maxX, item.x + item.width);
            current.minX = Math.min(current.minX, item.x);
        } else {
            lines.push(current);
            current = {
                text: item.str,
                y: item.y,
                minX: item.x,
                maxX: item.x + item.width,
                page: item.page
            };
        }
    }
    lines.push(current);
    return lines;
}

/**
 * Core Logic Step 3: Markdown Assembly
 * Decides when to merge lines into paragraphs and when to break.
 */
function assembleMarkdown(lines: VisualLine[]): string {
    if (lines.length === 0) return "";

    // 1. Statistics
    const stats = calculateStats(lines);
    const medianGap = stats.medianGap;
    const maxLineW = stats.maxWidth;

    let output = "";
    let buffer = "";

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        let text = line.text;

        // --- Block Structure Detection ---

        // Headings: (1) ... or (2) ...
        if (/^（\d+）/.test(text.trim())) {
            output += flush(buffer);
            buffer = "";
            output += `### ${text.trim()}\n\n`;
            continue;
        }

        // Links block
        if (text.includes("相关链接：")) {
            output += flush(buffer);
            buffer = "";

            // Lookahead for split URL
            let fullLink = text;
            let skip = 0;
            while (i + skip + 1 < lines.length) {
                const next = lines[i + skip + 1];
                if (isUrlContinuation(fullLink, next.text)) {
                    fullLink += next.text.trim();
                    skip++;
                } else {
                    break;
                }
            }
            i += skip;
            output += `> ${fullLink}\n\n`;
            continue;
        }

        // Review block
        if (text.startsWith("评述：")) {
            output += flush(buffer);
            buffer = "";
            output += `**评述：**\n`;
            text = text.replace("评述：", "").trim();
            if (!text) continue;
        }

        // --- Paragraph Merging ---

        if (buffer) {
            const prev = lines[i - 1];
            let shouldMerge = true;

            // Heuristic 1: Previous line ended with stop char AND was short
            // Meaning: "This is the end of a thought." -> Break.
            const prevEndsStop = /[。！？]/.test(buffer.trim().slice(-1));
            const prevIsShort = (prev.maxX - prev.minX) < (maxLineW * CONFIG.shortLineRatio);

            if (prevEndsStop && prevIsShort) {
                shouldMerge = false;
            }

            // Heuristic 2: Large vertical gap
            // Meaning: Visual separation -> Break.
            if (line.page === prev.page) {
                const gap = prev.y - line.y;
                if (gap > medianGap * CONFIG.paraGapMultiplier) {
                    shouldMerge = false;
                }
            }

            // Exception: URL continuation always merges
            if (isUrlContinuation(buffer, text)) {
                shouldMerge = true;
            }

            if (shouldMerge) {
                // Chinese concatenation (no space), English needs space
                const c1 = buffer.slice(-1);
                const c2 = text[0];
                const needsSpace = !isCJK(c1) && !isCJK(c2);
                buffer += (needsSpace ? " " : "") + text;
            } else {
                output += flush(buffer);
                buffer = text;
            }
        } else {
            buffer = text;
        }
    }

    output += flush(buffer);
    return output;
}

// --- Helpers ---

function calculateStats(lines: VisualLine[]) {
    let maxWidth = 0;
    const gaps: number[] = [];

    for (let i = 0; i < lines.length; i++) {
        const w = lines[i].maxX - lines[i].minX;
        if (w > maxWidth) maxWidth = w;

        if (i > 0 && lines[i].page === lines[i-1].page) {
            const gap = lines[i-1].y - lines[i].y;
            if (gap > 0 && gap < 100) gaps.push(gap);
        }
    }

    gaps.sort((a, b) => a - b);
    const medianGap = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 15.0;

    return { maxWidth, medianGap };
}

function flush(buffer: string) {
    if (!buffer) return "";
    // Clean up artifacts (e.g. bold markers if we used them, here we assume clean text)
    return buffer.trim() + "\n\n";
}

function isUrlContinuation(prev: string, next: string): boolean {
    // If prev looks like a URL start and next looks like a URL path
    const urlPattern = /(https?:\/\/|www\.)/;
    if (!urlPattern.test(prev)) return false;

    // Strict alphanumeric path check for next line
    return /^[a-zA-Z0-9\-\/\.\?\=\&\%]+$/.test(next.trim());
}

function isCJK(char: string) {
    return /[\u4e00-\u9fa5]/.test(char);
}

function die(msg: string) {
    console.error(`Error: ${msg}`);
    process.exit(1);
}

main();
