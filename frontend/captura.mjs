import { chromium } from "playwright";

const navegador = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const pagina = await navegador.newPage({ viewport: { width: 1440, height: 900 } });

const errores = [];
pagina.on("console", (m) => { if (m.type() === "error") errores.push(m.text()); });
pagina.on("pageerror", (e) => errores.push(String(e)));

await pagina.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
await pagina.waitForSelector("text=Cartera total", { timeout: 15000 });
await pagina.waitForTimeout(1200);

const texto = await pagina.locator("body").innerText();
console.log("=== TEXTO RENDERIZADO ===");
console.log(texto.slice(0, 1600));
console.log("\n=== ERRORES DE CONSOLA ===");
console.log(errores.length ? errores.join("\n") : "ninguno");

await pagina.screenshot({ path: "/home/user/proyecto_ejemplo/panel.png", fullPage: true });
await navegador.close();
