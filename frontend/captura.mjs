import { chromium } from "playwright";

const navegador = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const pagina = await navegador.newPage({ viewport: { width: 1440, height: 900 } });

const errores = [];
pagina.on("console", (m) => { if (m.type() === "error") errores.push(m.text()); });
pagina.on("pageerror", (e) => errores.push(String(e)));

const ver = async (hash, nombre, esperar) => {
  await pagina.goto(`http://127.0.0.1:5173/${hash}`, { waitUntil: "networkidle" });
  await pagina.waitForSelector(esperar, { timeout: 15000 });
  await pagina.waitForTimeout(900);
  await pagina.screenshot({ path: `/home/user/proyecto_ejemplo/${nombre}.png`, fullPage: true });
  console.log(`\n=== ${nombre} ===`);
  console.log((await pagina.locator("body").innerText()).slice(0, 900));
};

await ver("#/gestion", "lista", "text=Lista de gestión");

// Drill-down real: pulsar una fila tiene que llevar al cliente (§16).
await pagina.locator("tbody tr").first().click();
await pagina.waitForSelector("text=Facturas abiertas y alertas", { timeout: 10000 });
console.log("\n=== tras pulsar la primera fila ===");
console.log("hash:", await pagina.evaluate(() => location.hash));
await pagina.waitForTimeout(900);
await pagina.screenshot({ path: "/home/user/proyecto_ejemplo/cliente.png", fullPage: true });
console.log((await pagina.locator("body").innerText()).slice(0, 1100));

console.log("\n=== ERRORES DE CONSOLA ===");
console.log(errores.length ? errores.join("\n") : "ninguno");
await navegador.close();
