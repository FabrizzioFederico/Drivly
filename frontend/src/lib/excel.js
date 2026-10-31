// Genera un .xlsx real en el navegador. Un CSV no sirve para esto: no puede fijar anchos de columna (Excel muestra
// ##### en las fechas) y sus números dependen del separador decimal de cada Windows.

const XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
const ESTILO = { texto: 0, encabezado: 1, fecha: 2, importe: 3 };

const esc = (v) => String(v ?? '').replace(/[^\t\n\r\x20-￿]/g, '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** A -> 0, B -> 1... alcanza con 26 columnas. */
const letra = (i) => String.fromCharCode(65 + i);

/** Días desde 1899-12-30, en hora local: así guarda Excel las fechas. */
function serialDeFecha(iso) {
  const d = new Date(iso);
  return (Date.UTC(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes()) - Date.UTC(1899, 11, 30)) / 864e5;
}

function celda(ref, valor, tipo) {
  if (valor === null || valor === undefined || valor === '') return '';
  if (tipo === 'fecha') return `<c r="${ref}" s="${ESTILO.fecha}"><v>${serialDeFecha(valor)}</v></c>`;
  if (tipo === 'importe') return `<c r="${ref}" s="${ESTILO.importe}"><v>${Number(valor)}</v></c>`;
  return `<c r="${ref}" t="inlineStr" s="${ESTILO[tipo] ?? ESTILO.texto}"><is><t>${esc(valor)}</t></is></c>`;
}

function hoja(rows, columns) {
  const ultima = letra(columns.length - 1);
  const filas = [
    `<row r="1">${columns.map((c, i) => celda(`${letra(i)}1`, c.label, 'encabezado')).join('')}</row>`,
    ...rows.map((r, n) => `<row r="${n + 2}">${columns.map((c, i) => celda(`${letra(i)}${n + 2}`, c.value(r), c.tipo)).join('')}</row>`),
  ];
  return `${XML}<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">`
    + '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
    + `<cols>${columns.map((c, i) => `<col min="${i + 1}" max="${i + 1}" width="${c.ancho ?? 14}" customWidth="1"/>`).join('')}</cols>`
    + `<sheetData>${filas.join('')}</sheetData><autoFilter ref="A1:${ultima}${rows.length + 1}"/></worksheet>`;
}

const ESTILOS = `${XML}<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">`
  + '<numFmts count="2"><numFmt numFmtId="164" formatCode="dd/mm/yyyy\\ hh:mm"/><numFmt numFmtId="165" formatCode="&quot;$&quot;\\ #,##0.00"/></numFmts>'
  + '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FF0B0B0C"/><name val="Calibri"/></font></fonts>'
  + '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF00C2A8"/></patternFill></fill></fills>'
  + '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
  + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
  + '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
  + '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
  + '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
  + '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>';

function archivos(nombreHoja, rows, columns) {
  return {
    '[Content_Types].xml': `${XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">`
      + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
      + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
      + '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
      + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
    '_rels/.rels': `${XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">`
      + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    'xl/workbook.xml': `${XML}<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">`
      + `<sheets><sheet name="${esc(nombreHoja)}" sheetId="1" r:id="rId1"/></sheets></workbook>`,
    'xl/_rels/workbook.xml.rels': `${XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">`
      + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
      + '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
    'xl/styles.xml': ESTILOS,
    'xl/worksheets/sheet1.xml': hoja(rows, columns),
  };
}

const TABLA_CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(bytes) {
  let c = 0xFFFFFFFF;
  bytes.forEach((b) => { c = TABLA_CRC[(c ^ b) & 0xFF] ^ (c >>> 8); });
  return (c ^ 0xFFFFFFFF) >>> 0;
}

/** Un .xlsx es un zip de XML. Sin comprimir: el formato lo permite y son pocos kilobytes. */
function zip(entradas) {
  const texto = new TextEncoder();
  const partes = [];
  const central = [];
  let posicion = 0;
  const encabezado = (firma, campos) => {
    const b = new DataView(new ArrayBuffer(campos.reduce((t, [, largo]) => t + largo, 4)));
    b.setUint32(0, firma, true);
    let i = 4;
    campos.forEach(([valor, largo]) => {
      if (largo === 2) b.setUint16(i, valor, true); else b.setUint32(i, valor, true);
      i += largo;
    });
    return new Uint8Array(b.buffer);
  };

  Object.entries(entradas).forEach(([nombre, contenido]) => {
    const nombreB = texto.encode(nombre);
    const datos = texto.encode(contenido);
    const crc = crc32(datos);
    const comunes = [[20, 2], [0, 2], [0, 2], [0, 2], [0x21, 2], [crc, 4], [datos.length, 4], [datos.length, 4], [nombreB.length, 2], [0, 2]];
    const local = encabezado(0x04034B50, comunes);
    partes.push(local, nombreB, datos);
    central.push(encabezado(0x02014B50, [[20, 2], ...comunes, [0, 2], [0, 2], [0, 2], [0, 4], [posicion, 4]]), nombreB);
    posicion += local.length + nombreB.length + datos.length;
  });

  const largoCentral = central.reduce((t, p) => t + p.length, 0);
  const cantidad = Object.keys(entradas).length;
  return [...partes, ...central, encabezado(0x06054B50, [[0, 2], [0, 2], [cantidad, 2], [cantidad, 2], [largoCentral, 4], [posicion, 4], [0, 2]])];
}

/**
 * columns: [{ label, value(fila), tipo?: 'texto' | 'fecha' | 'importe', ancho? }]
 * `fecha` recibe un ISO y `importe` un número o su texto ("4080.00").
 */
export function descargarExcel(filename, nombreHoja, rows, columns) {
  const blob = new Blob(zip(archivos(nombreHoja, rows, columns)), { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
