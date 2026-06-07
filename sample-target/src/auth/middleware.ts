import type { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";

// SENSITIVE: this middleware enforces authentication for the whole API.
// Headroom requires human approval before an agent edits anything under src/auth/.
export function authMiddleware(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    return res.status(401).json({ error: "missing bearer token" });
  }

  const token = header.slice("Bearer ".length);
  try {
    const secret = process.env.JWT_SECRET;
    if (!secret) {
      return res.status(500).json({ error: "auth not configured" });
    }
    const payload = jwt.verify(token, secret);
    (req as Request & { user?: unknown }).user = payload;
    return next();
  } catch {
    return res.status(401).json({ error: "invalid token" });
  }
}
