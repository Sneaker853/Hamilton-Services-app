/**
 * Export data as a CSV file download.
 * @param {string} filename - Name for the downloaded file (without extension)
 * @param {string[]} headers - Column header labels
 * @param {Array<Array<string|number>>} rows - Array of row arrays
 */
export function downloadCsv(filename, headers, rows) {
  const escapeCsvField = (field) => {
    const str = String(field ?? '');
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const lines = [
    headers.map(escapeCsvField).join(','),
    ...rows.map((row) => row.map(escapeCsvField).join(','))
  ];

  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
