import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker?url';

GlobalWorkerOptions.workerSrc = pdfWorker;

function isPdf(file: File) {
  return (
    file.type === 'application/pdf' ||
    file.name.toLowerCase().endsWith('.pdf')
  );
}

async function extractPdfText(file: File): Promise<string> {
  const data = await file.arrayBuffer();
  const task = getDocument({ data });
  const pdf = await task.promise;
  const chunks: string[] = [];

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
    const page = await pdf.getPage(pageNumber);
    const content = await page.getTextContent();
    const pageText = content.items
      .map((item) => ('str' in item ? item.str : ''))
      .join(' ');
    chunks.push(`\n--- Page ${pageNumber} ---\n${pageText}`);
  }

  pdf.destroy();
  return chunks.join('\n');
}

export async function readFileAsText(file: File): Promise<string> {
  if (isPdf(file)) {
    try {
      return await extractPdfText(file);
    } catch (error) {
      console.warn('[documentParser] Failed to parse PDF, falling back to raw text.', error);
    }
  }

  return file.text();
}
