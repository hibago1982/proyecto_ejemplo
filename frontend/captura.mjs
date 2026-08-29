import { chromium } from "playwright";

const navegador = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const pagina = await navegador.newPage({ viewport: { width: 1440, height: 1000 } });
const errores = [];
pagina.on("console", (m) => { if (m.type() === "error") errores.push(m.text()); });
pagina.on("pageerror", (e) => errores.push(String(e)));

// Un cliente con varias facturas vencidas.
await pagina.goto("http://127.0.0.1:5173/#/clientes/90010000202", { waitUntil: "networkidle" });
await pagina.waitForSelector("text=Registrar gestión", { timeout: 15000 });

// Ciclo completo: acuerdo de pago con compromiso.
await pagina.selectOption('select:near(:text("Factura"))', "3002").catch(() => {});
await pagina.getByLabel(/^Tipo/).selectOption("acuerdo");
await pagina.getByLabel(/Resultado/).fill("Habla con tesorería, acepta pagar");
await pagina.getByLabel(/Observación/).fill("Pagará la mitad el 15 y el resto a fin de mes.");
await pagina.getByLabel(/Hubo compromiso de pago/).check();
await pagina.getByLabel(/Fecha comprometida/).fill("2026-09-15");
await pagina.getByLabel(/Valor comprometido/).fill("1600000");
await pagina.getByRole("button", { name: "Registrar" }).click();

await pagina.waitForSelector("text=Gestión registrada", { timeout: 10000 });
await pagina.waitForTimeout(1200);
await pagina.screenshot({ path: "/home/user/proyecto_ejemplo/gestion.png", fullPage: true });

const texto = await pagina.locator("body").innerText();
console.log("=== ESTADO TRAS REGISTRAR ===");
const i = texto.indexOf("FACTURAS ABIERTAS");
console.log(texto.slice(i, i + 700));
console.log("\n--- historial ---");
const h = texto.indexOf("HISTORIAL DE GESTIONES");
console.log(texto.slice(h, h + 400));
console.log("\n=== ERRORES DE CONSOLA ===");
console.log(errores.length ? errores.join("\n") : "ninguno");
await navegador.close();
