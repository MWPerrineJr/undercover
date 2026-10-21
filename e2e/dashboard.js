import { createServer } from "vite";

const server = await createServer({
  root: "dashboard",
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8010" },
  },
});
await server.listen();
