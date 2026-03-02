import { AuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const googleClientId = process.env.GOOGLE_CLIENT_ID ?? "";
const googleClientSecret = process.env.GOOGLE_CLIENT_SECRET ?? "";

export const authOptions: AuthOptions = {
  providers: [
    GoogleProvider({
      clientId: googleClientId,
      clientSecret: googleClientSecret,
      authorization: {
        params: {
          scope: [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.send",
          ].join(" "),
          access_type: "offline",
          prompt: "consent",
        },
      },
    }),
  ],
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account && profile) {
        token.googleId = (profile as { sub?: string }).sub;
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.accessTokenExpires = account.expires_at
          ? account.expires_at * 1000
          : undefined;
      }
      return token;
    },
    async session({ session, token }) {
      session.user = session.user ?? {};
      (session as Record<string, unknown>).accessToken = token.accessToken;
      (session.user as Record<string, unknown>).googleId = token.googleId;
      return session;
    },
    async signIn({ user, account, profile }) {
      if (!account || !profile) return false;

      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
      if (!backendUrl) return true;

      try {
        const tokenExpiry = account.expires_at
          ? new Date(account.expires_at * 1000).toISOString()
          : null;

        await fetch(`${backendUrl}/api/hosts/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            google_id: (profile as { sub?: string }).sub,
            email: user.email,
            name: user.name,
            picture: user.image,
            access_token: account.access_token,
            refresh_token: account.refresh_token,
            token_expiry: tokenExpiry,
          }),
        });
      } catch (err) {
        console.error("Failed to register host with backend:", err);
      }

      return true;
    },
  },
  pages: {
    signIn: "/auth/signin",
  },
};
