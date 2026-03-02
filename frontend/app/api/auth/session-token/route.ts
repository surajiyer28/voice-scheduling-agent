import { getToken } from "next-auth/jwt";
import { SignJWT } from "jose";
import { NextRequest, NextResponse } from "next/server";

// NextAuth encrypts its session JWT by default (JWE), which the Python backend
// can't decode. This route decrypts it server-side, then re-signs the relevant
// claims as a plain HS256 JWT that the backend can verify with python-jose.
export async function GET(req: NextRequest) {
  const decoded = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
    // raw: false (default) — decrypts the JWE and returns the payload object
  });

  if (!decoded) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!);
  const token = await new SignJWT({
    sub: decoded.sub as string,
    email: decoded.email as string,
    googleId: decoded.googleId as string,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(secret);

  return NextResponse.json({ token });
}
