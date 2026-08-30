import { chromium } from "playwright";

const navegador = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const ctx = await navegador.newContext({ viewport: { width: 1440, height: 950 } });
const pagina = await ctx.newPage();
const errores = [];
pagina.on("console", (m) => { if (m.type() === "error") errores.push(m.text()); });
pagina.on("pageerror", (e) => errores.push(String(e)));

const paso = (n) => console.log(`\n--- ${n} ---`);

await pagina.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });

paso("1. Pantalla de inicio de sesion");
await pagina.waitForSelector("text=Entrar", { timeout: 15000 });
await pagina.screenshot({ path: "/home/user/proyecto_ejemplo/entrar.png" });
console.log("visible sin sesion:", (await pagina.locator("body").innerText()).replace(/\n+/g, " | "));

paso("2. Credenciales incorrectas");
await pagina.getByLabel("Usuario").fill("admin");
await pagina.getByLabel("Clave").fill("equivocada");
await pagina.getByRole("button", { name: "Entrar" }).click();
await pagina.waitForSelector("text=Usuario o clave incorrectos", { timeout: 10000 });
console.log("rechazada correctamente");

paso("3. Entrar como gestor");
await pagina.getByLabel("Usuario").fill("gestor");
await pagina.getByLabel("Clave").fill("demo1234");
await pagina.getByRole("button", { name: "Entrar" }).click();
await pagina.waitForSelector("text=Cartera total", { timeout: 15000 });
const barra = await pagina.locator("nav").innerText();
console.log("barra:", barra.replace(/\n+/g, " | "));
await pagina.waitForTimeout(1000);
await pagina.screenshot({ path: "/home/user/proyecto_ejemplo/final_panel.png", fullPage: true });

paso("4. Drill-down a un cliente");
await pagina.locator("table tbody tr").first().click();
await pagina.waitForSelector("text=Registrar gestión", { timeout: 10000 });
console.log("hash:", await pagina.evaluate(() => location.hash));

paso("5. La sesion sobrevive a recargar");
await pagina.reload({ waitUntil: "networkidle" });
await pagina.waitForSelector("text=Registrar gestión", { timeout: 10000 });
console.log("sigue dentro tras recargar:", !(await pagina.locator("text=Entrar").count()));

paso("6. Salir borra la sesion");
await pagina.getByRole("button", { name: "Salir" }).click();
await pagina.waitForSelector("text=Entrar", { timeout: 10000 });
console.log("de vuelta al inicio de sesion");

console.log("\n=== ERRORES DE CONSOLA ===");
console.log(errores.length ? errores.join("\n") : "ninguno");
await navegador.close();
