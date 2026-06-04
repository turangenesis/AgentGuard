import express from "express";
import { authMiddleware } from "./auth/middleware";

const app = express();
app.use(express.json());

// Health check — public.
app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "taskflow-api" });
});

// Everything below requires a valid bearer token.
app.use(authMiddleware);

app.get("/tasks", (_req, res) => {
  res.json({ tasks: [] });
});

app.post("/tasks", (req, res) => {
  const { title } = req.body;
  if (!title) {
    return res.status(400).json({ error: "title is required" });
  }
  res.status(201).json({ id: "t_1", title });
});

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => {
  console.log(`taskflow-api listening on :${port}`);
});
